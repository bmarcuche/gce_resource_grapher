# -*- coding: utf-8 -*-

#The MIT License (MIT)
#
#Copyright (c) 2018 Bruno Marcuche
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

"""
Google Compute Engine Resource Usage Grapher
"""

import random
import threading
import webbrowser
import os
import json
import ast
import pygal
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials
from flask import Flask, render_template, redirect, url_for

class CustomInstanceError(Exception):
    """
    Error handler class for custom instance sizes
    """
    pass

class GCEStats(object):
    """
    Base class for GCE stats
    """
    def __init__(self):
        # load json configuration via env variable
        try:
            self.json = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            with open(self.json) as gce_creds:
                gce_params = json.load(gce_creds)
                self.project_id = gce_params['project_id']
        # failed to load json
        except IOError as ierr:
            raise ierr
        # failed to read os env var
        except KeyError:
            err = 'GOOGLE_APPLICATION_CREDENTIALS env variable is not set'
            raise KeyError(err)
        # custom image size dictionary
        self.instance_sizes = {}
        with open('custom_sizes.dict', 'r') as custom_sizes:
            for size in custom_sizes:
                self.instance_sizes.update(ast.literal_eval(size))
        self.credentials = GoogleCredentials.get_application_default()
        self.compute = discovery.build('compute', 'v1', credentials=self.credentials)
        self.custom_style = pygal.style.Style(background='#B7C9C7', plot_background='#B7C9C7')

    def get_instances(self):
        """
        Return a generator iterator of Google Cloud Engine instances
        """
        request = self.compute.instances().aggregatedList(project=self.project_id)
        while request is not None:
            response = request.execute()
            for instance in response['items'].values():
                for key in instance.keys():
                    if key != 'warning':
                        yield instance['instances']
            request = self.compute.instances().aggregatedList_next(
                previous_request=request,
                previous_response=response)

    def get_machine_types(self):
        """
        Return a generator iterator of GCE instance CPU and memory usage
        """
        request = self.compute.machineTypes().aggregatedList(project=self.project_id)
        while request is not None:
            response = request.execute()
            for machine_type in response['items'].values():
                for key in machine_type.keys():
                    if key != 'warning':
                        yield machine_type['machineTypes']
            request = self.compute.instances().aggregatedList_next(
                previous_request=request,
                previous_response=response)

    def get_disks(self):
        """
        Return a generator iterator of GCE instance disk space usage
        """
        request = self.compute.disks().aggregatedList(project=self.project_id)
        while request is not None:
            response = request.execute()
            for disk_type in response['items'].values():
                for key in disk_type.keys():
                    if key != 'warning':
                        yield disk_type['disks']
            request = self.compute.instances().aggregatedList_next(
                previous_request=request,
                previous_response=response)

    def merge_dicts(self):
        """
        Return a list of dictionaries of disk, memory and CPU per instance
        """
        mtypes = {}
        for machine_types in self.get_machine_types():
            for machine_type in machine_types:
                mtypes[machine_type['name']] = (machine_type['guestCpus'], machine_type['memoryMb'])
        instance_sizes = mtypes.copy()
        instance_sizes.update(self.instance_sizes)
        all_sizes = {}
        for instances in self.get_instances():
            for instance in instances:
                machine_type = instance['machineType'].split('/')[-1]
                region = ''.join(instance['zone'].split('/')[-1])
                all_sizes[instance['name']] = {}
                try:
                    all_sizes[instance['name']] = tuple(instance_sizes[machine_type]) + (region,)
                except KeyError as err:
                    raise CustomInstanceError(
                        'custom image size %s must be added to custom_sizes.dict'
                        % err)
        dtypes = {}
        for disk_sizes in self.get_disks():
            for disk_size in disk_sizes:
                dtypes[disk_size['name']] = (int(disk_size['sizeGb']),)
        all_dicts = [all_sizes, dtypes]
        merged = {}
        for k in all_sizes.iterkeys():
            merged[k] = tuple(merged[k] for merged in all_dicts)
        merged = {k: [element for tupl in v for element in tupl]
                  for k, v in merged.items()}
        all_map = [{u'host': k,
                    u'region': v[2],
                    u'cpu': v[0],
                    u'memory': v[1],
                    u'disk': v[3]} for k, v in merged.items()]
        return all_map

    def generate_graphs(self, region_in):
        """
        Graph CPU, memory and disk usage
        """
        instance_stats = self.merge_dicts()
        region_list = set([k['region'] for k in instance_stats])
        region_map = {}
        for region in region_list:
            sort_by_region = [x for x in instance_stats if x['region'] == region]
            region_map[region] = [x for x in sort_by_region]
        instances_by_region = {k: {u'Instances': len([x['host'] for x in v])}
                               for k, v
                               in region_map.items()}
        cpus_by_region = {k: {u'CPUs': sum([int(x['cpu']) for x in v])}
                          for k, v
                          in region_map.items()}
        disk_by_region = {k: {u'Disk (GB)': sum([int(x['disk']) for x in v])}
                          for k, v
                          in region_map.items()}
        mem_by_region = {k: {u'Memory (GB)': '%.2f' % sum([float(x['memory']) / 1024 for x in v])}
                         for k, v
                         in region_map.items()}
        all_cpu = sum([int(x['cpu']) for x in instance_stats])
        all_mem = sum([float(x['memory']) for x in instance_stats]) / 1024
        all_dsk = sum([int(x['disk']) for x in instance_stats])
        all_ins = len([x['host'] for x in instance_stats])
        app = Flask(__name__)

        @app.errorhandler(500)
        def page_not_found(_error):
            """
            Flask route for HTTP 500 errors
            """
            context = {}
            context['regions'] = sorted(region_list)
            return render_template('index.html', **context), 404

        @app.route('/index.html')
        def index():
            """
            Flask route for index template
            """
            context = {}
            context['regions'] = sorted(region_list)
            return render_template('index.html', **context)

        @app.route('/favicon.ico')
        def favicon():
            """
            Flask route sending favicon.ico to summary template
            """
            return redirect(url_for('summary'))

        @app.route('/')
        def homepage():
            """
            Flask default route
            """
            return redirect(url_for('summary'))

        @app.route('/<region_in>')
        def region_cpu_instances(region_in):
            """
            Flask route for resource counts per region
            """
            kwargs = {}
            kwargs[u'width'] = 900
            kwargs[u'height'] = 400
            kwargs[u'explicit_size'] = True
            kwargs[u'print_values'] = True
            kwargs[u'style'] = self.custom_style
            title = u'Resource Usage for %s' % region_in
            # create instances and cpu chart
            resource_chart = pygal.HorizontalBar(title=title, **kwargs)
            for instance, instance_count in instances_by_region[region_in].items():
                resource_chart.add(instance, instance_count)
            for cpu, cpu_count in cpus_by_region[region_in].items():
                resource_chart.add(cpu, cpu_count)
            # create memory and disk chart
            mem_disk_chart = pygal.HorizontalBar(title=title, **kwargs)
            for mem, mem_count in mem_by_region[region_in].items():
                mem_disk_chart.add(mem, float(mem_count))
            for disk, disk_count in disk_by_region[region_in].items():
                mem_disk_chart.add(disk, disk_count)
            context = {}
            context[u'title'] = title
            context[u'resource_chart'] = resource_chart
            context[u'mem_disk_chart'] = mem_disk_chart
            return render_template('region.html', region_name=region_in, **context)

        @app.route('/summary')
        def summary():
            """
            Flask route for total instance resource counts graph
            """
            kwargs = {}
            kwargs[u'width'] = 750
            kwargs[u'height'] = 300
            kwargs[u'explicit_size'] = True
            kwargs[u'print_values'] = True
            kwargs[u'style'] = self.custom_style
            title = u'Instance Count By Region'
            instance_chart = pygal.Bar(title=title, **kwargs)
            for instance, instance_count in instances_by_region.items():
                instance_chart.add(instance, instance_count.values()[0])
            title = u'CPU Count By Region'
            cpu_chart = pygal.Bar(title=title, **kwargs)
            for cpu, cpu_count in cpus_by_region.items():
                cpu_chart.add(cpu, cpu_count.values()[0])
            title = u'Disk Usage By Region (GB)'
            disk_chart = pygal.Bar(title=title, **kwargs)
            for disk, disk_count in disk_by_region.items():
                disk_chart.add(disk, disk_count.values()[0])
            title = u'Memory Usage By Region (GB)'
            mem_chart = pygal.Bar(title=title, **kwargs)
            for mem, mem_count in mem_by_region.items():
                mem_chart.add(mem, float(mem_count.values()[0]))
            title = u'Instance And CPU Count All Regions'
            instance_cpu_chart = pygal.Bar(title=title, **kwargs)
            instance_cpu_chart.add(u'Instances', all_ins)
            instance_cpu_chart.add(u'CPUs', all_cpu)
            title = u'Memory and Disk Usage All Regions (GB)'
            mem_disk_chart = pygal.Bar(title=title, **kwargs)
            mem_disk_chart.add(u'Memory', all_mem)
            mem_disk_chart.add(u'Disk', all_dsk)
            context = {}
            context[u'title'] = title
            context[u'region_name'] = region_in
            context[u'instance_chart'] = instance_chart
            context[u'cpu_chart'] = cpu_chart
            context[u'disk_chart'] = disk_chart
            context[u'mem_chart'] = mem_chart
            context[u'instance_cpu_chart'] = instance_cpu_chart
            context[u'mem_disk_chart'] = mem_disk_chart
            return render_template(u'summary.html', **context)
        port = 5000 + random.randint(0, 999)
        url = "http://127.0.0.1:%d" % port
        threading.Timer(1.25, lambda: webbrowser.open_new_tab(url + os.sep + region_in)).start()
        app.run(debug=False, port=port)

if __name__ == '__main__':
    STATS = GCEStats()
    STATS.generate_graphs('summary')
