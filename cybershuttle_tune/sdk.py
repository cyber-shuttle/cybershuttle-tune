from cybershuttle_tune.cli.auth import do_authorization_flow, get_access_token
from cybershuttle_tune.cli.main import download_experiment
from cybershuttle_tune.airavata_operator import AiravataOperator
import cybershuttle_tune.sweeper as sweeper

import os
import random
import string
import configparser

def authorize(config_file_location = "settings.ini"):
    do_authorization_flow(config_file_location)

def generate_random_job_name(length = 6):
    characters = string.ascii_letters + string.digits    
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string

class ExecutionContext:
    def __init__(self, resource, project, group_resource_profile, cpu, memory, queue):
        self.resource = resource
        self.project = project
        self.group_resource_profile = group_resource_profile
        self.cpu = cpu
        self.memory = memory
        self.queue = queue
        
class ApplicationContext:
    def __init__(self, app_name, input_dir):
        self.app_name = app_name
        self.input_dir = input_dir
        
class TuneConfig:
    def __init__(self, 
                 app_context, params, 
                 execution_context, 
                 gateway_config_file='settings.ini',
                 working_directory='workdir'):
        self.app_context = app_context
        self.params = params
        self.execution_context = execution_context
        self.gateway_config_file = gateway_config_file
        self.working_directory = working_directory
        
class DiscreteParam:
    def __init__(self, name, values):
        self.name = name
        self.values = values
        
class RangeParam:
    def __init__(self, start, end, step):
        self.start = start
        self.end = end
        self.step = step
        
def run_grid_search(tune_config):
    
    job_name = generate_random_job_name()
    
    if not os.path.exists(tune_config.working_directory):
        os.makedirs(tune_config.working_directory)

    all_variable_values = sweeper.generate_inputs(job_name=job_name, template_dir=tune_config.app_context.input_dir,
                                parameter_values=tune_config.params, working_dir=tune_config.working_directory)

    return sweeper.sweep_params(access_token=get_access_token(), job_name=job_name,
                             application_name=tune_config.app_context.app_name,
                             computation_resource_name=tune_config.execution_context.resource,
                             working_dir=tune_config.working_directory,
                             config_file_location=tune_config.gateway_config_file,
                             all_variable_values=all_variable_values)
    
def get_sweep_status(job_name, working_dir, config_file_location = 'settings.ini'):
    return sweeper.get_sweep_status(get_access_token(), job_name, working_dir, config_file_location)

def fetch_outputs(job_name, working_dir, config_file_location = 'settings.ini'):
    states, indexes = sweeper.get_sweep_status(get_access_token(), job_name, working_dir, config_file_location)
    exp_ids_to_download = []
    for state, index in zip(states, indexes):
        if state[1] == 'COMPLETED':
            exp_ids_to_download.append((state[0], index))

    config = configparser.ConfigParser()
    config.read(config_file_location)
    gateway_url = config.get('Gateway', 'GATEWAY_URL')

    output_dirs = []
    for (exp_id, index) in exp_ids_to_download:
        print("Downloading experiment " + exp_id + " for job index " + str(index))
        output_path = working_dir + "/" + job_name + "/"  + str(index) + "/outputs"
        download_experiment(get_access_token(), gateway_url, exp_id, output_path)
        output_dirs.append(output_path)
        
    return output_dirs