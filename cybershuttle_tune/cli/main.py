import typer
import cgi
import cybershuttle_tune.parser as parser
import cybershuttle_tune.airavata_operator as operator
import cybershuttle_tune.sweeper as sweeper
import cybershuttle_tune.param_types as param_types
import termios
import configparser
import sys
from pick import pick
import os
from tabulate import tabulate
import zipfile
import io
import requests
import base64
from pathlib import Path
from .auth import get_access_token_or_error
from .auth import do_authorization_flow
from .auth import get_access_token
import subprocess

app = typer.Typer()

def read_long_line(prompt=""):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~termios.ICANON
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        line = input(prompt)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return line

@app.command("config")
def config():

    config_file_location = typer.prompt("Config file location", "settings.ini")
    access_token, auth_code = do_authorization_flow(config_file_location)

    config = configparser.ConfigParser()
    #config.read(config_file_location)
    #auth_url = config.get('KeycloakServer', 'LOGIN_DESKTOP_URI')
    #access_token = read_long_line("Go to " + auth_url + " and paste the access token here: ")

    config = configparser.ConfigParser()
    config['Default'] = {
        'CONFIG_FILE_LOCATION': os.path.abspath(config_file_location),
        'ACCESS_TOKEN': access_token,
        'AUTH_CODE': auth_code
    }

    cstune_config_dir = os.path.join(os.path.expanduser('~'), ".cstune")

    if not os.path.exists(cstune_config_dir):
        os.makedirs(cstune_config_dir)

    cstune_config_file = os.path.join(cstune_config_dir, 'credentials')

    with open(cstune_config_file, 'w') as configfile:
        config.write(configfile)

def get_config():
    cstune_config_dir = os.path.join(os.path.expanduser('~'), ".cstune")
    cstune_config_file = os.path.join(cstune_config_dir, 'credentials')

    if not os.path.exists(cstune_config_file):
        print("Cstune was not configured. Run cstune config")
        sys.exit()

    config = configparser.ConfigParser()
    config.read(cstune_config_file)
    config_file_location = config.get('Default', 'CONFIG_FILE_LOCATION')
    auth_code = config.get('Default', 'AUTH_CODE')

    return config_file_location, get_access_token(), auth_code

@app.command("start")
def start():

    config_file_location, access_token, auth_code = get_config()

    airavata_operator = operator.AiravataOperator(config_file_location)
    applications = airavata_operator.get_application_list(access_token)
    app_options = [app.appModuleName for app in applications]
    option, index = pick(app_options, "Select the Application", indicator="=>")
    selected_module_id = applications[index].appModuleId
    selected_application_name = option

    deployments = airavata_operator.get_compatible_deployments(access_token, selected_module_id)
    compute_host_ids = [dp.computeHostId for dp in deployments]

    compute_resources = airavata_operator.get_compute_resources(access_token, compute_host_ids)
    compute_resource_names = [cr.hostName for cr in compute_resources]

    option, index = pick(compute_resource_names, "Select the Compute Resource", indicator="=>")
    selected_compute_resource = compute_resources[index]
    selected_compute_resource_name = option
    selected_deployment = deployments[index]

    templates_input_directory = typer.prompt("Input templates directory", "inputs")
    template_files = [f for f in os.listdir(templates_input_directory) if not os.path.isdir(f)]

    variables = set()
    for template_file in template_files:
        variables = variables.union(parser.parse_file(os.path.join(templates_input_directory, template_file)))

    parameter_values = []

    for variable in variables:
        variable_options = ["Integer", "Float", "String"]
        option, index = pick(variable_options, "What is the type of variable " + variable + "?", indicator="=>")
        values_string = typer.prompt("Provide values for " + variable + " with space separation")
        values_arr = values_string.split(" ")
        if option == 'Integer':
            values_int = [int(val) for val in values_arr]
            param_type = param_types.IntParamType(name= variable, values=values_int)
        elif option == "Float":
            values_float = [float(val) for val in values_arr]
            param_type = param_types.FloatParamType(name= variable, values=values_float)
        else:
            param_type = param_types.StringParamType(name= variable, values=values_arr)

        parameter_values.append(param_type)

    exp_name = typer.prompt("Provide a unique name for the experiment")
    working_directory = typer.prompt("Working directory to prepare inputs", "workdir")

    print("Preparing inputs....")
    all_variable_values = sweeper.generate_inputs(job_name=exp_name, template_dir=templates_input_directory,
                            parameter_values=parameter_values, working_dir=working_directory)

    print("Submitting jobs to the cluster...")
    sweeper.sweep_params(access_token=access_token, job_name=exp_name,
                         application_name=selected_application_name,
                         computation_resource_name=selected_compute_resource_name,
                         working_dir=working_directory,
                         config_file_location=config_file_location,
                         all_variable_values=all_variable_values)

    print(all_variable_values)

@app.command("status")
def status():
    config_file_location, access_token, auth_code = get_config()
    working_dir = typer.prompt("Working directory", "workdir")
    job_name = typer.prompt("Job Name")
    states, _ = sweeper.get_sweep_status(access_token, job_name, working_dir, config_file_location)
    headers = ["Experiment Id", "State"]
    print(tabulate(states, headers= headers, tablefmt="grid"))

@app.command("outputs")
def output():
    config_file_location, access_token, auth_code = get_config()
    working_dir = typer.prompt("Working directory", "workdir")
    job_name = typer.prompt("Job Name")
    states, indexes = sweeper.get_sweep_status(access_token, job_name, working_dir, config_file_location)
    exp_ids_to_download = []
    for state, index in zip(states, indexes):
        if state[1] == 'COMPLETED':
            exp_ids_to_download.append((state[0], index))

    config = configparser.ConfigParser()
    config.read(config_file_location)
    gateway_url = config.get('Gateway', 'GATEWAY_URL')

    print(exp_ids_to_download)

    for (exp_id, index) in exp_ids_to_download:
        download_experiment(access_token, gateway_url, exp_id, working_dir + "/" + job_name + "/"  + str(index) + "/outputs")

@app.command("analyze")
def analyze():
    config_file_location, access_token, auth_code = get_config()
    working_dir = typer.prompt("Working directory", "workdir")
    job_name = typer.prompt("Job Name")
    #script_path = typer.prompt("Script Path")
    open_jupyter_notebook(working_dir + "/" + job_name)


def open_jupyter_notebook(notebook_dir):
    try:
        nb_process = subprocess.Popen(["jupyter", "notebook", "--notebook-dir", notebook_dir])
        nb_process.wait()
    except FileNotFoundError:
        print("Jupyter Notebook is not installed or not in your PATH.")

def download_experiment(get_access_token, gateway_url, experiment_id, output_dir="./workdir"):
    headers = {"Authorization": f"Bearer {get_access_token}"}
    r = requests.get(
        f"{gateway_url}/sdk/download-experiment-dir/{experiment_id}/",
        headers=headers,
    )
    print(f"Result {r.status_code}: {r.reason}")
    r.raise_for_status()
    # get name of zip file as returned in HTTP response headers and name the output directory the same
    disposition = r.headers["Content-Disposition"]
    disp_value, disp_params = cgi.parse_header(disposition)
    filename, ext = os.path.splitext(disp_params["filename"])
    output_dir = Path(output_dir) / filename

    zipped = zipfile.ZipFile(io.BytesIO(r.content))
    zipped.extractall(output_dir)
    return output_dir

if __name__ == "__main__":
    app()