import pandas as pd
import zipfile
import os
from pathlib import Path
import shutil

def split_csv_and_zip(input_file_path: Path, rows_per_chunk: int, output_dir: Path) -> Path:
    """
    Splits a CSV file into multiple chunks and zips each chunk.
    Returns the path to the final ZIP file containing all zipped chunks.
    """
    base_name = input_file_path.stem
    
    # Create a temporary directory for chunks and zips
    temp_working_dir = output_dir / f"csv_split_temp_{os.getpid()}"
    temp_working_dir.mkdir(parents=True, exist_ok=True)

    chunk_num = 1
    all_zipped_chunk_paths = []
    
    for chunk in pd.read_csv(input_file_path, chunksize=rows_per_chunk):
        # Create chunk filename
        chunk_filename = f"{base_name}_part{chunk_num}.csv"
        chunk_path = temp_working_dir / chunk_filename
        
        # Save chunk to CSV
        chunk.to_csv(chunk_path, index=False)
        
        # Create zip filename
        zip_filename = f"{base_name}_part{chunk_num}.zip"
        zip_path = temp_working_dir / zip_filename
        
        # Zip the chunk
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(chunk_path, chunk_filename)
        
        # Remove the temporary CSV chunk
        os.remove(chunk_path)
        
        all_zipped_chunk_paths.append(zip_path)
        chunk_num += 1
    
    # Create a final master zip file containing all the individual chunk zips
    master_zip_filename = output_dir / f"{base_name}_split_chunks.zip"
    with zipfile.ZipFile(master_zip_filename, 'w', zipfile.ZIP_DEFLATED) as master_zipf:
        for zipped_chunk_path in all_zipped_chunk_paths:
            master_zipf.write(zipped_chunk_path, zipped_chunk_path.name)
    
    # Clean up the temporary working directory
    shutil.rmtree(temp_working_dir)

    return master_zip_filename

if __name__ == "__main__":
    # Example usage (for testing purposes)
    # Create a dummy CSV file
    dummy_data = {
        'col1': range(1, 100001),
        'col2': [f'data_{i}' for i in range(1, 100001)]
    }
    dummy_df = pd.DataFrame(dummy_data)
    dummy_csv_path = Path("dummy.csv")
    dummy_df.to_csv(dummy_csv_path, index=False)

    output_directory = Path(".")
    rows_per_chunk = 10000

    print(f"Splitting {dummy_csv_path} into chunks of {rows_per_chunk} rows...")
    final_zip_path = split_csv_and_zip(dummy_csv_path, rows_per_chunk, output_directory)
    print(f"Final zipped file created at: {final_zip_path}")

    # Clean up dummy CSV
    os.remove(dummy_csv_path)
