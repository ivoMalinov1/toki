## download_stp_profiles

Function is a scheduled event triggered once a Year on 15 Jan every year to import the stp profiles data into a google cloud storage bucket

### _download_stp_profiles(request)_

- the files should be put in the Raw Data folder on the shared drive in the location: stp_profiles/STP-profile-weights-2022 in corresponding folders for each ERP.

- the function once triggered it will save the files in a google cloud storage bucket named stp_profiles_toki-data-platform

- Required Python version: 3.10
