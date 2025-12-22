import pandas as pd
import os
from pathlib import Path

def split_multiline_rows(df):
    """
    Split rows containing multi-line cells (cells with newlines) into separate rows.
    For each row, if any cell contains newlines, create multiple rows where:
    - Cells with newlines are split across the new rows
    - Cells without newlines are copied to all new rows
    
    Args:
        df: pandas DataFrame to process
        
    Returns:
        pandas DataFrame with multi-line cells split into separate rows
    """
    new_rows = []
    
    for idx, row in df.iterrows():
        # Check if any cell in this row contains newlines
        has_newlines = any(isinstance(val, str) and '\n' in val for val in row)
        
        if not has_newlines:
            # No newlines, keep row as is
            new_rows.append(row.to_dict())
        else:
            # Split cells with newlines
            # First, determine the maximum number of lines in any cell
            max_lines = 1
            split_cells = {}
            
            for col in df.columns:
                val = row[col]
                if isinstance(val, str) and '\n' in val:
                    # Split by newline
                    lines = val.split('\n')
                    split_cells[col] = lines
                    max_lines = max(max_lines, len(lines))
                else:
                    # Single value, will be repeated
                    split_cells[col] = [val]
            
            # Create new rows
            for line_idx in range(max_lines):
                new_row = {}
                for col in df.columns:
                    cell_lines = split_cells[col]
                    if line_idx < len(cell_lines):
                        # Use the corresponding line
                        new_row[col] = cell_lines[line_idx]
                    else:
                        # Use the last line if we've run out (shouldn't happen often)
                        new_row[col] = cell_lines[-1]
                new_rows.append(new_row)
    
    # Create new DataFrame from the rows
    result_df = pd.DataFrame(new_rows)
    
    # Preserve the original column order
    result_df = result_df[df.columns]
    
    return result_df

def convert_xlsx_to_csv():
    """
    Convert all XLSX files in the input directory to CSV files in the output directory.
    Splits rows with multi-line cells into separate rows.
    """
    
    # Define the input and output directories
    # These are the folder paths where your files are located
    input_dir = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\reference\incident_code_files\xlsx"
    output_dir = r"C:\Users\ccharm\Desktop\Data\txr_replay_automation\reference\incident_code_files\csv"

    # Convert string paths to Path objects for easier file handling
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Check if the input directory exists
    if not input_path.exists():

        print(f"Error: Input directory does not exist: {input_dir}")
        return
    
    # Create the output directory if it doesn't exist
    # exist_ok=True means it won't raise an error if the directory already exists
    output_path.mkdir(parents=True, exist_ok=True)
    print(f"Output directory ready: {output_dir}")
    
    # Find all XLSX files in the input directory
    # glob("*.xlsx") searches for all files ending with .xlsx
    xlsx_files = list(input_path.glob("*.xlsx"))
    
    if not xlsx_files:
        print(f"No XLSX files found in {input_dir}")
        return
    
    print(f"Found {len(xlsx_files)} XLSX file(s) to convert:")
    
    # Counter to track successful conversions
    successful_conversions = 0
    
    # Loop through each XLSX file and convert it
    for xlsx_file in xlsx_files:
        try:
            print(f"Converting: {xlsx_file.name}")
            
            # Read the XLSX file using pandas
            # This reads only the first sheet by default
            df = pd.read_excel(xlsx_file)
            
            # Format date columns to DD/MM/YYYY format (without time)
            for col in df.columns:
                if df[col].dtype == 'datetime64[ns]' or pd.api.types.is_datetime64_any_dtype(df[col]):
                    # Convert datetime columns to DD/MM/YYYY format
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%d/%m/%Y')
            
            # Split rows with multi-line cells into separate rows
            df = split_multiline_rows(df)
            
            # Create the output filename by changing the extension from .xlsx to .csv
            csv_filename = xlsx_file.stem + ".csv"  # .stem gives filename without extension
            csv_filepath = output_path / csv_filename
            
            # Save the data as a CSV file
            # index=False means we don't save the row numbers as a column
            # encoding='utf-8-sig' adds BOM for proper UTF-8 recognition in Excel
            df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
            
            print(f"  ✓ Successfully converted to: {csv_filename}")
            successful_conversions += 1
            
        except Exception as e:
            # If there's an error with any file, print the error but continue with other files
            print(f"  ✗ Error converting {xlsx_file.name}: {str(e)}")
    
    # Print summary of the conversion process
    print(f"\nConversion complete!")
    print(f"Successfully converted: {successful_conversions}/{len(xlsx_files)} files")
    print(f"CSV files saved to: {output_dir}")

# This is the main execution block
# It only runs when you execute this script directly (not when importing it)
if __name__ == "__main__":
    print("XLSX to CSV Converter")
    print("=" * 30)
    convert_xlsx_to_csv()
    
    # Keep the console window open so you can see the results
    input("\nPress Enter to close...")
