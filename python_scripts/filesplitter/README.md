# CSV Splitter & Zipper GUI

This is a Python application with a graphical user interface (GUI) that allows you to split large CSV files into smaller chunks and then compress each chunk into a separate ZIP file. This is particularly useful for handling large datasets that might exceed email attachment limits or for easier distribution.

## Features

*   **User-Friendly Interface:** Built with `tkinter` for an intuitive experience.
*   **CSV Splitting:** Divides a large CSV file into multiple smaller CSV files based on a specified number of rows per chunk.
*   **Automatic Zipping:** Each generated CSV chunk is automatically compressed into its own ZIP archive.
*   **Progress Tracking:** Provides a log output and an indeterminate progress bar to keep you informed during the processing.
*   **Error Handling:** Basic error handling for invalid inputs and file operations.
*   **Responsive GUI:** Uses threading to ensure the GUI remains responsive during file processing.

## How it Works

1.  **Select CSV File:** Browse and select the large CSV file you wish to split.
2.  **Set Rows per Chunk:** Specify how many rows each output CSV file should contain. The GUI provides a hint for approximate ZIP file size (e.g., "~10MB per zip" for 100,000 rows).
3.  **Split & Zip:** Click the "Split & Zip File" button to start the process.
4.  **Output:** The application will create several `.zip` files in the same directory as the original CSV, each containing a part of your original data. A log will display the progress and details of the created files.

## Requirements

To run this application, you need the following Python libraries:

*   `tkinter` (usually comes pre-installed with Python)
*   `pandas`
*   `pathlib` (part of standard library)
*   `zipfile` (part of standard library)
*   `os` (part of standard library)
*   `threading` (part of standard library)

You can install `pandas` using pip:

```bash
pip install pandas
```

## Usage

1.  Save the provided Python code as `csv_splitter_gui.py`.
2.  Run the script from your terminal:

    ```bash
    python csv_splitter_gui.py
    ```
3.  The GUI window will appear.
4.  Click "Browse..." to select your CSV file.
5.  Enter the desired number of rows per chunk.
6.  Click "Split & Zip File" to begin.
7.  Monitor the "Output Log" for progress and completion messages.

## Example

If you have a file named `large_data.csv` and you set "Rows per chunk" to `100000`, the application might generate files like:

*   `large_data_part1.zip` (containing `large_data_part1.csv`)
*   `large_data_part2.zip` (containing `large_data_part2.csv`)
*   ...and so on.

Each `.zip` file will be approximately 10MB (depending on your data) and ready for sharing.
