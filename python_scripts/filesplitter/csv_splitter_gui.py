import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
import pandas as pd
import zipfile
import os
from pathlib import Path
import threading

class CSVSplitterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Splitter & Zipper")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        self.selected_file = None
        self.processing = False
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="CSV File Splitter & Zipper", 
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # File selection
        ttk.Label(main_frame, text="Select CSV File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.file_label = ttk.Label(main_frame, text="No file selected", 
                                     foreground="gray", wraplength=400)
        self.file_label.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        
        self.browse_btn = ttk.Button(main_frame, text="Browse...", command=self.browse_file)
        self.browse_btn.grid(row=1, column=2, padx=5)
        
        # Rows per chunk
        ttk.Label(main_frame, text="Rows per chunk:").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        self.rows_var = tk.StringVar(value="100000")
        rows_entry = ttk.Entry(main_frame, textvariable=self.rows_var, width=15)
        rows_entry.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(main_frame, text="(~10MB per zip)", foreground="gray").grid(row=2, column=2, sticky=tk.W)
        
        # Process button
        self.process_btn = ttk.Button(main_frame, text="Split & Zip File", 
                                       command=self.process_file, state=tk.DISABLED)
        self.process_btn.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Log output
        ttk.Label(main_frame, text="Output Log:").grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
        
        self.log_text = scrolledtext.ScrolledText(main_frame, height=15, width=80, state=tk.DISABLED)
        self.log_text.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            self.selected_file = filename
            self.file_label.config(text=os.path.basename(filename), foreground="black")
            self.process_btn.config(state=tk.NORMAL)
            self.log(f"Selected: {filename}")
    
    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def process_file(self):
        if not self.selected_file or self.processing:
            return
        
        try:
            rows_per_chunk = int(self.rows_var.get())
            if rows_per_chunk <= 0:
                raise ValueError("Rows per chunk must be positive")
        except ValueError as e:
            self.log(f"Error: Invalid rows per chunk value - {e}")
            return
        
        # Disable button and start progress
        self.processing = True
        self.process_btn.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        
        # Run in separate thread to keep GUI responsive
        thread = threading.Thread(target=self.split_and_zip, args=(rows_per_chunk,))
        thread.start()
    
    def split_and_zip(self, rows_per_chunk):
        try:
            input_file = self.selected_file
            base_name = Path(input_file).stem
            output_dir = Path(input_file).parent
            
            self.log(f"\nProcessing {os.path.basename(input_file)}...")
            self.log(f"Rows per chunk: {rows_per_chunk}")
            
            chunk_num = 1
            zip_files_created = []
            
            for chunk in pd.read_csv(input_file, chunksize=rows_per_chunk):
                # Create chunk filename
                chunk_filename = f"{base_name}_part{chunk_num}.csv"
                chunk_path = output_dir / chunk_filename
                
                # Save chunk to CSV
                chunk.to_csv(chunk_path, index=False)
                
                # Create zip filename
                zip_filename = f"{base_name}_part{chunk_num}.zip"
                zip_path = output_dir / zip_filename
                
                # Zip the chunk
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(chunk_path, chunk_filename)
                
                # Remove the temporary CSV chunk
                os.remove(chunk_path)
                
                # Check zip size
                zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
                zip_files_created.append((zip_filename, zip_size_mb))
                
                self.log(f"Created {zip_filename} ({zip_size_mb:.2f} MB, {len(chunk):,} rows)")
                
                chunk_num += 1
            
            self.log(f"\n✓ Complete! Created {len(zip_files_created)} zip files in:")
            self.log(f"  {output_dir}")
            self.log("\nFiles created:")
            for filename, size in zip_files_created:
                self.log(f"  - {filename}: {size:.2f} MB")
            
            self.log("\nAll files are ready to attach to emails!")
            
        except Exception as e:
            self.log(f"\n✗ Error: {str(e)}")
        
        finally:
            # Re-enable button and stop progress
            self.processing = False
            self.progress.stop()
            self.process_btn.config(state=tk.NORMAL)
            self.browse_btn.config(state=tk.NORMAL)


def main():
    root = tk.Tk()
    app = CSVSplitterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
