import base64
import os
import platform
import tempfile
import subprocess
import io
import threading
import traceback
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

APP_TITLE = "S3 Label Viewer (Base64 PNG)"
DEFAULT_BUCKET = "pat-labels"
DEFAULT_PROFILE = "gateway"


def human_error(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e) or 'No details'}"


class S3LabelViewer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.geometry("1100x700")
        self.minsize(900, 580)

        # AWS/S3
        self.session = None
        self.s3 = None
        self.bucket = DEFAULT_BUCKET
        self.region = ""
        self.profile = ""
        self.current_prefix = ""
        self.photo_ref = None  # Keep reference for Tk image
        self.loading = False
        self.last_image = None
        self.last_image_key = ""

        # Layout
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        self._build_controls()
        self._build_browser()
        self._build_viewer()

        # Auto-connect
        self.after(150, self.connect_s3)

    def _build_controls(self):
        panel = ctk.CTkFrame(self)
        panel.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 6))
        panel.grid_columnconfigure(10, weight=1)

        self.profile_entry = ctk.CTkEntry(panel, placeholder_text="AWS profile (optional)")
        self.profile_entry.grid(row=0, column=0, padx=(10, 6), pady=8)
        self.profile_entry.insert(0, DEFAULT_PROFILE)

        self.region_entry = ctk.CTkEntry(panel, placeholder_text="AWS region (optional)")
        self.region_entry.grid(row=0, column=1, padx=6, pady=8)

        self.bucket_entry = ctk.CTkEntry(panel, placeholder_text="Bucket", width=220)
        self.bucket_entry.insert(0, DEFAULT_BUCKET)
        self.bucket_entry.grid(row=0, column=2, padx=6, pady=8)

        self.connect_btn = ctk.CTkButton(panel, text="Connect", command=self.connect_s3)
        self.connect_btn.grid(row=0, column=3, padx=6, pady=8)

        self.up_btn = ctk.CTkButton(panel, text="Up", command=self.go_up_dir, state="disabled", width=70)
        self.up_btn.grid(row=0, column=4, padx=(6, 10), pady=8)

        self.search_entry = ctk.CTkEntry(panel, placeholder_text="Search term (optional)", width=220)
        self.search_entry.grid(row=0, column=5, padx=6, pady=8)
        self.search_btn = ctk.CTkButton(panel, text="Search", command=self.on_search_click)
        self.search_btn.grid(row=0, column=6, padx=(6, 10), pady=8)

        self.status_label = ctk.CTkLabel(panel, text="Status: Not connected", anchor="w")
        self.status_label.grid(row=0, column=10, sticky="ew", padx=(6, 10))

    def _build_browser(self):
        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, sticky="nsw", padx=(10, 6), pady=(0, 10))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(left, text="Bucket Browser", font=ctk.CTkFont(size=14, weight="bold"))
        title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.tree = ttk.Treeview(left, columns=("type", "key"), show="tree")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 0))
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_expand)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=1, column=1, sticky="ns", pady=(0, 0))

        xscroll = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=xscroll.set)
        xscroll.grid(row=2, column=0, sticky="ew", padx=(10, 0))

        self.root_node = self.tree.insert("", "end", text=f"s3://{DEFAULT_BUCKET}/", open=True, values=("dir", ""))

    def _build_viewer(self):
        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 10), pady=(0, 10))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(right, text="Label Preview", font=ctk.CTkFont(size=14, weight="bold"))
        title.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.save_btn = ctk.CTkButton(right, text="Save PNG", command=self.on_save_png, state="disabled", width=90)
        self.save_btn.grid(row=0, column=1, padx=(0, 10), pady=(10, 0), sticky="e")

        self.canvas_frame = ctk.CTkFrame(right)
        self.canvas_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.canvas_frame.bind("<Configure>", lambda e: self._resize_image_to_frame())

        self.image_label = ctk.CTkLabel(self.canvas_frame, text="No image loaded")
        self.image_label.pack(expand=True, fill="both")

        self.meta_label = ctk.CTkLabel(right, text="", anchor="w", wraplength=700)
        self.meta_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

    def set_status(self, text: str):
        self.status_label.configure(text=f"Status: {text}")

    def set_loading(self, loading: bool):
        self.loading = loading
        state = "disabled" if loading else "normal"
        self.connect_btn.configure(state=state)
        self.up_btn.configure(state=state if self.current_prefix else "disabled")
        self.set_status("Loading..." if loading else "Ready")

    # ========== AWS / S3 ==========

    def connect_s3(self):
        if self.loading:
            return
        self.set_loading(True)

        self.profile = self.profile_entry.get().strip()
        self.region = self.region_entry.get().strip()
        self.bucket = self.bucket_entry.get().strip() or DEFAULT_BUCKET

        def worker():
            try:
                if self.profile:
                    self.session = boto3.Session(profile_name=self.profile, region_name=self.region or None)
                else:
                    self.session = boto3.Session(region_name=self.region or None)
                self.s3 = self.session.client("s3")
                self.s3.head_bucket(Bucket=self.bucket)
                self.current_prefix = ""
                self.after(0, self._reset_tree_root)
                self._list_prefix("")  # prime cache
            except Exception as e:
                tb = traceback.format_exc(limit=1)
                self.after(0, lambda e=e, tb=tb: messagebox.showerror("Connection error", f"{human_error(e)}\n\n{tb}"))
                self.after(0, lambda: self.set_status("Connect failed"))
            finally:
                self.after(0, lambda: self.set_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _reset_tree_root(self):
        for c in self.tree.get_children(""):
            self.tree.delete(c)
        self.root_node = self.tree.insert("", "end", text=f"s3://{self.bucket}/", open=True, values=("dir", ""))
        self.tree.insert(self.root_node, "end", text="Loading...", values=("placeholder", ""))
        self.tree.item(self.root_node, open=True)
        self.on_tree_expand(None, node=self.root_node)

    def on_tree_expand(self, event, node=None):
        if node is None:
            node = self.tree.focus() or self.root_node
        vals = self.tree.item(node, "values")
        if not vals:
            return
        node_type, prefix = vals[0], vals[1] if len(vals) > 1 else ""
        if node_type != "dir":
            return

        # Don't re-fetch if already populated, unless it's a placeholder
        children = self.tree.get_children(node)
        if children and self.tree.item(children[0], "values")[0] != "placeholder":
            return

        for c in children:
            self.tree.delete(c)

        self.set_loading(True)

        def worker():
            try:
                folders, files = self._list_prefix(prefix)

                def populate():
                    for f in folders:
                        n = self.tree.insert(node, "end", text=f, values=("dir", prefix + f))
                        self.tree.insert(n, "end", text="...", values=("placeholder", ""))
                    for key in files:
                        self.tree.insert(node, "end", text=key.split("/")[-1], values=("file", key))
                    
                    # Scroll back to the parent node that was expanded
                    self.tree.see(node)

                self.after(0, populate)
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("List error", human_error(e)))
            finally:
                self.after(0, lambda: self.set_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def on_tree_select(self, event):
        node = self.tree.focus()
        vals = self.tree.item(node, "values")
        if not vals:
            return
        node_type, key = vals[0], vals[1] if len(vals) > 1 else ""
        if node_type == "dir":
            self.current_prefix = key
            self.up_btn.configure(state="normal" if self.current_prefix else "disabled")

    def on_tree_double_click(self, event):
        node = self.tree.focus()
        vals = self.tree.item(node, "values")
        if not vals:
            return
        node_type, key = vals[0], vals[1] if len(vals) > 1 else ""
        if node_type == "dir":
            self.on_tree_expand(None, node=node)
        elif node_type == "file" and key.lower().endswith(".png"):
            self.load_and_show_image(key)

    def go_up_dir(self):
        if not self.current_prefix:
            return
        p = self.current_prefix[:-1] if self.current_prefix.endswith("/") else self.current_prefix
        parent = "/".join(p.split("/")[:-1])
        new_prefix = parent + "/" if parent else ""
        self.current_prefix = new_prefix
        self._reset_tree_root()
        self.up_btn.configure(state="normal" if self.current_prefix else "disabled")

    def _list_prefix(self, prefix: str):
        paginator = self.s3.get_paginator("list_objects_v2")
        folders = set()
        files = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for common in page.get("CommonPrefixes", []):
                name = common["Prefix"][len(prefix):]
                folders.add(name)
            for item in page.get("Contents", []):
                key = item["Key"]
                if key == prefix:
                    continue
                remainder = key[len(prefix):]
                if "/" in remainder:
                    continue
                files.append(key)
        return sorted(folders), sorted(files)

    def _list_prefix_sorted(self, prefix: str):
        paginator = self.s3.get_paginator("list_objects_v2")
        folders = {}
        files = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
            for common in page.get("CommonPrefixes", []):
                child_prefix = common["Prefix"]
                newest = None
                inner = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=child_prefix, MaxKeys=1)
                for obj in inner.get("Contents", []):
                    newest = obj.get("LastModified")
                folders[child_prefix[len(prefix):]] = newest
            for item in page.get("Contents", []):
                key = item["Key"]
                if key == prefix:
                    continue
                remainder = key[len(prefix):]
                if "/" in remainder:
                    continue
                files.append((key, item.get("LastModified")))
        sorted_folders = sorted(folders.items(), key=lambda kv: (kv[1] is None, kv[1]), reverse=True)
        sorted_files = sorted(files, key=lambda t: (t[1] is None, t[1]), reverse=True)
        return [name for name, _ in sorted_folders], [key for key, _ in sorted_files]

    def on_search_click(self):
        term = self.search_entry.get().strip()
        if not term:
            messagebox.showinfo("Search", "Enter a search term (part of folder or file name).")
            return
        if not self.s3:
            messagebox.showerror("Not connected", "Connect to S3 first.")
            return
        self.set_loading(True)

        def worker():
            try:
                found_key = self._search_newest_first(self.current_prefix, term)
                if found_key:
                    self.after(0, lambda k=found_key: self.load_and_show_image(k))
                else:
                    self.after(0, lambda: messagebox.showinfo("Search", "No matching PNG found."))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("Search error", human_error(e)))
            finally:
                self.after(0, lambda: self.set_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _search_newest_first(self, prefix: str, term: str):
        _, files = self._list_prefix_sorted(prefix)
        for key in files:
            name = key.split("/")[-1]
            if term.lower() in name.lower() and name.lower().endswith(".png"):
                return key
        folders, _ = self._list_prefix_sorted(prefix)
        for f in folders:
            child_prefix = prefix + f
            if not child_prefix.endswith("/"):
                child_prefix += "/"
            match = self._search_newest_first(child_prefix, term)
            if match:
                return match
        return None

    # ========== Image Loading / Decoding ==========

    def load_and_show_image(self, key: str):
        if self.loading:
            return
        self.set_loading(True)

        def worker():
            try:
                obj = self.s3.get_object(Bucket=self.bucket, Key=key)
                raw = obj["Body"].read()

                img_bytes = None
                try:
                    text = raw.decode("utf-8", errors="strict").strip()
                except UnicodeDecodeError:
                    text = None

                if raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    img_bytes = raw
                elif text is not None:
                    if text.startswith("data:image/png;base64,"):
                        text = text.split(",", 1)[1].strip()
                    b64 = "".join(text.split())
                    try:
                        img_bytes = base64.b64decode(b64, validate=True)
                    except (base64.binascii.Error, ValueError):
                        img_bytes = base64.b64decode(b64, validate=False)
                else:
                    try:
                        img_bytes = base64.b64decode(raw, validate=True)
                    except Exception:
                        img_bytes = raw

                image = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                self.last_image = image.copy()
                self.last_image_key = key
                self.after(0, lambda img=image, k=key: self._display_image(img, k))
            except (ClientError, BotoCoreError, OSError, ValueError) as e:
                self.after(0, lambda e=e: messagebox.showerror("Image error", human_error(e)))
            finally:
                self.after(0, lambda: self.set_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _display_image(self, pil_image: Image.Image, key: str):
        frame_w = max(self.canvas_frame.winfo_width(), 200)
        frame_h = max(self.canvas_frame.winfo_height(), 200)
        img_w, img_h = pil_image.size

        scale = min(frame_w / img_w, frame_h / img_h, 1.0)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))
        resized = pil_image.resize((new_w, new_h), Image.LANCZOS)

        tk_img = ImageTk.PhotoImage(resized)
        self.photo_ref = tk_img
        self.image_label.configure(image=tk_img, text="")
        self.meta_label.configure(text=f"s3://{self.bucket}/{key}  |  {pil_image.size[0]}x{pil_image.size[1]}")
        self.save_btn.configure(state="normal")

    def _resize_image_to_frame(self):
        if isinstance(self.photo_ref, ImageTk.PhotoImage):
            pass

    def on_save_png(self):
        try:
            if not self.last_image:
                messagebox.showinfo("Save PNG", "No image loaded to save.")
                return

            # Generate default filename from S3 key
            default_name = self.last_image_key.split("/")[-1] if self.last_image_key else "label.png"
            if not default_name.lower().endswith(".png"):
                default_name += ".png"

            # Open file dialog
            file_path = filedialog.asksaveasfilename(
                title="Save PNG As",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                initialfile=default_name
            )

            if not file_path:  # User cancelled
                return

            # Save the image
            self.last_image.convert("RGB").save(file_path, format="PNG")
            messagebox.showinfo("Save PNG", f"Image saved successfully to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Save Error", human_error(e))


if __name__ == "__main__":
    app = S3LabelViewer()
    app.mainloop()