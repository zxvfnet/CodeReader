"""Read multiple QR codes and barcodes from images and export them as CSV.

The package is split so that the GUI only depends on plain functions:

- ``decoder``: decode every code in one image.
- ``files``: expand files/folders and decode them in a batch.
- ``csv_writer``: write the results as an Excel-friendly CSV file.
"""
