import typer
import cybershuttle_tune.parser as parser
import cybershuttle_tune.airavata_operator as operator
import cybershuttle_tune.sweeper as sweeper
import cybershuttle_tune.param_types as param_types
import termios
import configparser
import sys
from pick import pick
import os

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
@app.command("start")
def start():
    config_file_location = typer.prompt("Config file location", "settings.ini")
    config = configparser.ConfigParser()
    config.read(config_file_location)
    auth_url = config.get('KeycloakServer', 'LOGIN_DESKTOP_URI')
    access_token = read_long_line("Go to " + auth_url + " and paste the access token here: ")

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
    sweeper.generate_inputs(job_name=exp_name, template_dir=templates_input_directory,
                            parameter_values=parameter_values, working_dir=working_directory)

    print("Submitting jobs to the cluster...")
    sweeper.sweep_params(access_token=access_token, job_name=exp_name,
                         application_name=selected_application_name,
                         computation_resource_name=selected_compute_resource_name,
                         working_dir=working_directory,
                         config_file_location=config_file_location)


if __name__ == "__main__":
    app()