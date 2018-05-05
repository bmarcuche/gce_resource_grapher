# GCE Resource Usage Grapher

GCERUG allows visualization of Google Compute Engine instance usage. It currently graphs instance, CPU, memory and disk space count with options for filtering by region or total summary.

#### Total Resource Counts

<p align="center">
  <img width="700" height="600" src="https://github.com/bmarcuche/gce_resource_grapher/blob/master/doc/gce_summary_stats.png">
</p>

#### Resource Counts by Region

<p align="center">
  <img width="700" height="600" src="https://github.com/bmarcuche/gce_resource_grapher/blob/master/doc/gce_stats_by_region.png">
</p>

#### Available Regions Listing

<p align="center">
  <img width="700" height="200" src="https://github.com/bmarcuche/gce_resource_grapher/blob/master/doc/gce_by_region.png">
</p>

# Getting started

## Requirements

GCERUG was written in `python2.7` and requires the following modules
* pygal
* flask
* google-api-python-client
* oauth2client

The script will attempt to load GCE's service file using the GOOGLE_APPLICATION_CREDENTIALS enviromnent variable. 
More information on configuring the GCE environment can be found on https://cloud.google.com/compute/docs/access/create-enable-service-accounts-for-instances,

### Authentication

If you have the json service file available, you can export the GOOGLE_APPLICATION_CREDENTIALS environment variable by pointing it to your service file
```
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/gce_service_file.json
```
### Running the script
GCERUG will attempt to open a new tab on your default webbrowser.  
```
python2.7 gce_resource_grapher.py
```
*Note for Windows Users*  This script works under Windows WLS but you'll need some additional enviornment variables configured.  

The example assumes firefox should be configured as the default browser; edit accordingly.
```
export DISPLAY=:0.0
export BROWSER='/mnt/c/Program Files/Firefox/firefox.exe'
````
### Example Execution
```
bruno@boxee ~/gce_resource_grapher $ python2.7 gce_resource_grapher.py 
 * Serving Flask app "gce_resource_grapher" (lazy loading)
 * Environment: production
   WARNING: Do not use the development server in a production environment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://127.0.0.1:5940/ (Press CTRL+C to quit)
Created new window in existing browser session.
127.0.0.1 - - [05/May/2018 15:39:10] "GET /summary HTTP/1.1" 200 -
127.0.0.1 - - [05/May/2018 15:39:10] "GET /static/styles/style.css HTTP/1.1" 200 -
127.0.0.1 - - [05/May/2018 15:39:10] "GET /favicon.ico HTTP/1.1" 302 -
127.0.0.1 - - [05/May/2018 15:39:10] "GET /summary HTTP/1.1" 200 -
```
At this point your browser should be open to the graphs summary page.  If not, you can still navigate directly to URL listed in your terminal output.

# Configuration
### Custom Instance Sizes
GCERUG will query the GCE API to build a map of image sizes.  If you build instances with non-default sizes, you'll need to add the custom size mapping to the `custom_sizes.dict` file.

Custom size should be a dictionary data type
```
{u'custom-1-2560': (1, 2560)}
{u'custom-1-6656': (1, 6656)}
{u'custom-2-10240': (2, 10240)}
{u'custom-4-10240': (4, 10240)}
```
