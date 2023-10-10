import cybershuttle_tune.parser as parser
import cybershuttle_tune.airavata_operator as operator
import itertools
import os

def generate_inputs(job_name, template_dir, parameter_values, working_dir):

    template_files = [f for f in os.listdir(template_dir) if not os.path.isdir(f)]

    all_variable_values = []
    param_grid = get_grid(parameter_values)
    for grid_idx in range(len(param_grid)):
        variable_values = {}
        for param_val_idx in range(len(parameter_values)):
            param_val = parameter_values[param_val_idx]
            variable_values[param_val.name] = param_grid[grid_idx][param_val_idx]
        all_variable_values.append(variable_values)

    job_input_path = os.path.join(working_dir, job_name)
    if os.path.exists(job_input_path):
        raise Exception("Job input path " + job_input_path + " already exists")

    for job_idx in range(len(all_variable_values)):
        input_dir = os.path.join(job_input_path, str(job_idx))
        os.makedirs(input_dir)
        cur_variable_values = all_variable_values[job_idx]
        for template_file in template_files:
            content = parser.apply_values(
                file_path=os.path.join(template_dir, template_file),
                variable_values=cur_variable_values)

            with open(os.path.join(input_dir, template_file), "w") as text_file:
                text_file.write(content)

    print(all_variable_values)

def sweep_params(access_token, job_name, application_name,
                 computation_resource_name, working_dir, config_file_location):

    job_input_path = os.path.join(working_dir, job_name)

    sub_dirs = os.listdir(job_input_path)

    for sub_dir in sub_dirs:
        local_input_path = os.path.join(job_input_path, sub_dir)
        airavata_op = operator.AiravataOperator(config_file_location)

        ex_id = airavata_op.submit_experiment(access_token=access_token,
                                      experiment_name=job_name + "_" + sub_dir,
                                      application_name=application_name,
                                      computation_resource_name=computation_resource_name,
                                      local_input_path=local_input_path)

        with open(os.path.join(job_input_path, "summary.txt"), 'a+') as f:
            f.write(sub_dir + ":" + ex_id + "\n")
        print(ex_id)



def get_grid(parameter_values):
    vals_arr = []
    for param_val in parameter_values:
        vals_arr.append(param_val.values)

    return list(itertools.product(*vals_arr))
