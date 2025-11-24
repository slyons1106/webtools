# S3 Label Viewer

This is a desktop application for browsing and viewing PNG label files stored in an AWS S3 bucket. It is built with Python, using customtkinter for the graphical user interface, and boto3 for interacting with AWS S3.

## Features

*   Connect to a specified AWS S3 bucket using an AWS profile.
*   Browse the bucket content in a hierarchical tree view.
*   View PNG images, including raw and base64 encoded PNGs.
*   Save the viewed images to your local machine.
*   Search for files within the current S3 path.

## Prerequisites

Before you can run this application, you need to have the following installed:

*   Python 3
*   The required Python libraries

You also need to have your AWS credentials configured. The application uses the AWS credentials file (`~/.aws/credentials`) to connect to your AWS account. You can specify an AWS profile to use in the application.

## Installation

1.  **Clone the repository or download the `downloader.py` file.**

2.  **Install the required Python libraries:**

    ```bash
    pip install customtkinter boto3 Pillow
    ```

## How to Run

To run the application, execute the following command in your terminal from the directory where you saved the `downloader.py` file:

```bash
python downloader.py
```

## How to Use

1.  **Launch the application.**
2.  **Enter your AWS profile name** (if you are not using the default profile).
3.  **Enter the S3 bucket name** you want to browse.
4.  **Click the "Connect" button.** The application will connect to your S3 bucket and display the root directory in the "Bucket Browser".
5.  **Browse the bucket** by expanding the directories in the tree view.
6.  **Double-click on a PNG file** to view it in the "Label Preview" panel.
7.  **Click the "Save PNG" button** to save the currently displayed image to your computer.
8.  **Use the search bar** to find files within the current directory and its subdirectories.

## Recent Changes

*   **Improved Tree View Scrolling:** The folder tree no longer loses focus when a folder is expanded.
*   **Fixed Save Dialog Error:** Corrected a bug that caused an error when saving PNG files.
*   **Adjusted Layout:** The "Bucket Browser" and "Label Preview" panels are now in a 60/40 split, giving the browser more space.