import os
import glob
from osgeo import gdal

def compress_geotiffs(input_folder_name='images', output_folder_name='images_compressed'):
    """
    Finds all GeoTIFF files in an input folder, compresses them,
    and saves them to an output folder. This version is more robust and
    includes enhanced debugging and path handling.
    """
    # --- Robust Path Handling ---
    # Get the absolute path of the directory where this script is located.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create absolute paths for the input and output folders relative to the script's location.
    # This ensures the script works regardless of where it's called from.
    input_folder = os.path.join(script_dir, input_folder_name)
    output_folder = os.path.join(script_dir, output_folder_name)

    print(f"Script location: {script_dir}")
    print(f"Searching for images in: {input_folder}")

    # --- Enhanced Debugging ---
    # Check if the input folder actually exists
    if not os.path.isdir(input_folder):
        print(f"\n[ERROR] The directory '{input_folder}' was not found.")
        print("Please ensure a folder named 'images' exists in the same directory as this script.")
        return
        
    # List all contents of the directory to see what the script finds
    try:
        directory_contents = os.listdir(input_folder)
        if not directory_contents:
            print(f"\nThe '{input_folder}' directory exists, but it is empty.")
        else:
            print(f"\nFound the following files/folders in '{input_folder_name}': {directory_contents}")
    except Exception as e:
        print(f"Could not read the contents of the '{input_folder}' directory. Reason: {e}")
        return

    # --- Configuration ---
    # Search for all common TIFF extensions (.tif, .TIF, .tiff)
    search_patterns = ["*.TIF", "*.tif", "*.tiff"]
    tif_files = []
    for pattern in search_patterns:
        search_path = os.path.join(input_folder, pattern)
        tif_files.extend(glob.glob(search_path))

    # Exit if no TIF files are found
    if not tif_files:
        print(f"\n[ERROR] No files with .tif, .TIF, or .tiff extensions were found in the '{input_folder_name}' directory.")
        return

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output directory: {output_folder}")

    # --- Compression Options ---
    # Option 1: Lossless LZW compression (commented out)
    # translate_options = gdal.TranslateOptions(
    #     format='GTiff',
    #     creationOptions=['COMPRESS=LZW', 'TILED=YES']
    # )

    # Option 2: Lossy JPEG compression with 8-bit scaling
    # This fixes the "BitsPerSample 16 not allowed" error by converting
    # the 16-bit data to 8-bit (0-255) before compression.
    translate_options = gdal.TranslateOptions(
        format='GTiff',
        creationOptions=['COMPRESS=JPEG', 'JPEG_QUALITY=85', 'TILED=YES'],
        outputType=gdal.GDT_Byte,  # Convert output to 8-bit
        scaleParams=[[]]           # Auto-scale from input min/max to 0-255
    )

    print(f"\nFound {len(tif_files)} files to compress...")

    # --- Processing Loop ---
    for filepath in tif_files:
        filename = os.path.basename(filepath)
        output_filepath = os.path.join(output_folder, filename)
        print(f"  Compressing '{filename}'...")
        try:
            gdal.Translate(output_filepath, filepath, options=translate_options)
        except Exception as e:
            print(f"    [ERROR] Could not process {filename}. Reason: {e}")

    print(f"\nCompression complete. All processed files saved in '{output_folder}'.")


if __name__ == "__main__":
    compress_geotiffs()
