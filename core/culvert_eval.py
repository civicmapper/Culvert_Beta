"""
Culvert Evaluation Model

Main interface script

"""

# --------------------------------------------------------------------------
# IMPORTS

# standard library
import os, re, csv, time, sys
# external dependencies
import numpy, click
# package imports
from .logic import runoff, capacity_prep, capacity, return_periods, loader, sorter, loader

# --------------------------------------------------------------------------
# HELPERS

def county_loader(counties_table, counties_signature=None):
    """
    A helper function reads in the counties file and validates inputs. It
    returns a python list containing dictionaries that provide access to files
    used by `culvert_eval`.
    """
    # Prompts user to input county file name, and corrects to proper '.csv' format
    # data_path = raw_input('Enter path to Data folder, for example: C:\Users\Tanvi\Desktop\Cornell_CulvertModel_StartKit_Nov2016\All_Scripts\: ')
    #TO DO: return data path to Noah's original (data folder Scripts folder/county abbreviation folder/data folder)
    # counties_table = raw_input('Enter name of counties csv file in the Data folder: ')
    # counties_table = data_path + counties_table
    if counties_table[len(counties_table) - 4:] != '.csv':
        counties_table = counties_table + '.csv'

    # Signature for the county list csv file.
    # This creates a list of dictionaries that stores the relevant headers of
    # the input file and the type of data in the column under that header
    if not counties_signature:
        counties_signature = [
            {'name': 'county_abbreviation', 'type': str},
            #eg: The first element of the list 'counties_signature' is a dictionary for
            #county abbreviation. 'county_abbreviation' is the header of a column of data
            #we want to extract from the input file, containing data of type string
            {'name': 'watershed_data_filename', 'type': str},
            {'name': 'watershed_precipitation_tablename', 'type': str},
            {'name': 'field_data_filename', 'type': str}
        ];

    # Load and validate county file data.
    # county_data will now store the relevant data from the counties csv input file
    # in the format described in loader.py using the signature defined above.
    # valid_rows will store all value for the key 'valid_rows' in the dictionary geometry_data
    county_data = loader.load(counties_table, counties_signature, 1, -1)
    counties = county_data["valid_rows"]
    invalid_counties = county_data["invalid_rows"]

    # Notify of any invalid counties and exit if present.
    if len(invalid_counties) > 0:
        click.echo("\nERROR: Bailing out due to invalid county rows in '{0}':".format(counties_table))
        for invalid in invalid_counties :
            click.echo("* Row number {0} was invalid because {1}".format(
                str(invalid["row_number"]),
                invalid["reason_invalid"]
            ))
        #sys.exit(0)
        return None
    else:
        return counties

# --------------------------------------------------------------------------
# CLI functions


@click.command()
@click.argument('culvert_watershed_table')
@click.argument('watershed_precipitation_table')
@click.argument('field_data_collection_table')
@click.option('--a', default="area", help="name of area")
@click.option('--d', default=os.getcwd(), help="Analysis output directory.", type=click.Path())
def culvert_eval(
    culvert_watershed_table,
    watershed_precipitation_table,
    field_data_collection_table,
    a, #county_name,
    d #output_directory
):

    click.echo('Cornell Culvert Evaluation Model')
    click.echo('--------------------------------\n')

    county_name = a
    output_directory = d

    # Create path and filenames for all of the output files:
    output_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    output_path = os.path.join(output_directory,county_name,"outputs",output_time)
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    #Notifies user about running calculations
    click.echo("Running calculations for {0}:".format(county_name))

    # 1. WATERSHED PEAK DISCHARGE

    # Sort watersheds so they match original numbering (GIS changes numbering)
    sorted_watershed_table = os.path.join(output_path, "sorted_ws.csv")
    click.echo(" * Sorting watersheds by BarrierID and saving it to {0}.".format(sorted_watershed_table))
    sorter.sort(culvert_watershed_table, county_name, sorted_watershed_table)

    # Culvert Peak Discharge function calculates the peak discharge for each culvert for current and future precip
    current_runoff_table = os.path.join(output_path, "current_runoff.csv")
    future_runoff_table = os.path.join(output_path, "future_runoff.csv")
    click.echo("Calculating current runoff and saving it to {0}".format(current_runoff_table))
    runoff.calculate(sorted_watershed_table, watershed_precipitation_table, 1.0, current_runoff_table)
    click.echo(" * Calculating future runoff and saving it to {0}".format(future_runoff_table))
    runoff.calculate(sorted_watershed_table, watershed_precipitation_table, 1.15, future_runoff_table) # 1.15 times the rain in the future.

    # 2. CULVERT GEOMETRY
    # Culvert Capacity Prep function calculates the cross sectional area and assigns c and Y coeffs to each culvert
    click.echo(" * Calculating culvert geometry and saving it to {0}".format(culvert_geometry_table))
    capacity_prep.geometry(field_data_collection_table, culvert_geometry_table)

    # 3. CULVERT CAPACITY
    # Culvert_Capacities function calculates the capacity of each culvert (m^3/s) based on inlet control
    culvert_geometry_table = os.path.join(output_path, "culv_geom.csv")
    click.echo(" * Calculating culvert capacity and saving it to {0}".format(capacity_table))
    capacity.inlet_control(culvert_geometry_table, capacity_table)

    # 4. RETURN PERIODS AND FINAL OUTPUT
    capacity_table = os.path.join(output_path, "capacity_output.csv")
    return_period_table = os.path.join(output_path, "return_periods.csv")
    final_output_table = os.path.join(output_path, "model_output.csv")

    click.echo(" * Calculating return periods and saving them to {0}".format(return_period_table))
    click.echo(" * Calculating final output and saving it to {0}".format(final_output_table))
    # Run return period script
    return_periods.return_periods(
        capacity_table,
        current_runoff_table,
        future_runoff_table,
        return_period_table,
        final_output_table
    )
    click.echo("Done!\nAll output files can be found within the folder {0}".format(output))

@click.command()
@click.argument('counties_table')
@click.argument('output_directory')
def county_processing(counties_table, output_directory):
    """
    Runs the culvert evaluation model over multiple geographies; typically
    county-sized geographies are most appropriate.

    Inputs:

    - `counties_table`: a `csv` file formatted with 4 columns containing this
    type of information:

    0. A name for the geography (e.g., the county name)
    
    1. Culvert Watershed data input: A CSV file containing data on
    culvert watershed characteristics including Culvert IDs, WS_area in
    sq km, Tc in hrs and CN
    
    2. NRCC export CSV file of precipitation data (in) for the 1, 2, 5,
    10, 25, 50, 100, 200 and 500 yr 24-hr storm events. Check that the
    precipitation from the 1-yr, 24 hr storm event is in cell K-11
    
    3. Field data collection input: A CSV file containing culvert data
    gathered in the field using either then NAACC data collection
    format or Tompkins county Fulcrum app

    All paths in the csv file must be full paths (i.e., from root)

    - `output_directory`: a path on disk where outputs will be written.

    Outputs:

    These are not explicitly set by the user, but written to the
    `output_directory`:

    1. Culvert geometry file: A CSV file containing culvert dimensions
    and assigned c and Y coefficients
    
    2. Capacity output: A CSV file containing the maximum capacity of
    each culvert under inlet control
    
    3. Current Runoff output: A CSV file containing the peak discharge
    for each culvert's watershed for the analyzed return period storms
    under current rainfall conditions
    
    4. Future Runoff output: A CSV file containing the peak discharge
    for each culvert's watershed for the analyzed return period storms
    under 2050 projected rainfall conditions
    
    5. Return periods output: A CSV file containing the maximum return
    period that each culvert can safely pass under current rainfall
    conditions and 2050 projections.
    
    6. Final Model ouptut: A CSV file that summarizes the above model
    outputs in one table
    """

    click.echo('Cornell Culvert Evaluation Model (Batch Processing)')
    click.echo('--------------------------------\n')
    # Parse the inputs from the counties table (csv)
    counties = county_loader(counties_table)
    # For each county in the counties table, perform all the computations:
    for county in counties:
        # run the each_watershed function
        culvert_eval(
            culvert_watershed_table=county["watershed_data_filename"],
            watershed_precipitation_table=county["watershed_precipitation_tablename"],
            field_data_collection_table=county["field_data_filename"],
            w=county["county_abbreviation"],
            d=output_directory
        )