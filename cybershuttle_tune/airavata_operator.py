from airavata_sdk.clients.api_server_client import APIServerClient
import jwt
from airavata.model.security.ttypes import AuthzToken
from airavata_sdk.transport.settings import GatewaySettings, ExperimentSettings
from airavata_sdk.clients.utils.api_server_client_util import APIServerClientUtil
from airavata_sdk.clients.utils.data_model_creation_util import DataModelCreationUtil
from airavata_sdk.clients.sftp_file_handling_client import SFTPConnector
import logging
import os

logger = logging.getLogger('airavata_sdk.clients')
logger.setLevel(logging.INFO)

class AiravataOperator:

    def __init__(self, configuration_file_location):
        self.configuration_file_location = configuration_file_location
        self.api_server_client = APIServerClient(configuration_file_location)
        self.gateway_conf = GatewaySettings(configuration_file_location)
        self.experiment_conf = ExperimentSettings(configuration_file_location)

    def get_airavata_token(self, access_token, gateway_id):
        decode = jwt.decode(access_token, options={"verify_signature": False})
        self.user_id = decode['preferred_username']
        claimsMap = {
            "userName": self.user_id,
            "gatewayID": gateway_id
        }

        return  AuthzToken(accessToken=access_token, claimsMap=claimsMap)
    def get_application_list(self, access_token):
        airavata_token = self.get_airavata_token(access_token, self.gateway_conf.GATEWAY_ID)
        modules = self.api_server_client.get_all_app_modules(airavata_token, self.gateway_conf.GATEWAY_ID)
        return modules

    def get_compatible_deployments(self, access_token, application_module_id):
        airavata_token = self.get_airavata_token(access_token, self.gateway_conf.GATEWAY_ID)

        api_util = APIServerClientUtil(self.configuration_file_location,
                                       self.user_id, "",
                                       self.gateway_conf.GATEWAY_ID,
                                       access_token)
        grp_id = api_util.get_group_resource_profile_id(self.experiment_conf.GROUP_RESOURCE_PROFILE_NAME)
        deployments = self.api_server_client.get_application_deployments_for_app_module_and_group_resource_profile(
            airavata_token, application_module_id, grp_id)

        return deployments

    def get_compute_resources(self, access_token, resource_ids):
        airavata_token = self.get_airavata_token(access_token, self.gateway_conf.GATEWAY_ID)
        resources = []
        for resource_id in resource_ids:
            resources.append(self.api_server_client.get_compute_resource(airavata_token, resource_id))

        return resources

    def get_group_resource_profile_id(self, access_token, group_resource_profile_name):
        airavata_token = self.get_airavata_token(access_token, self.gateway_conf.GATEWAY_ID)
        response = self.api_server_client.get_group_resource_list(airavata_token, self.gateway_conf.GATEWAY_ID)
        for x in response:
            if x.groupResourceProfileName == group_resource_profile_name:
                return x.groupResourceProfileId
        return None
    def submit_experiment(self, access_token,
                          experiment_name,
                          application_name,
                          computation_resource_name,
                          local_input_path,
                          input_file_mapping = {},
                          queue_name = None,
                          node_count = None,
                          cpu_count = None,
                          walltime=None,
                          auto_schedule=False):
        airavata_token = self.get_airavata_token(access_token, self.gateway_conf.GATEWAY_ID)

        api_util = APIServerClientUtil(self.configuration_file_location,
                                       self.user_id, "",
                                       self.gateway_conf.GATEWAY_ID,
                                       access_token)
        data_model_util = DataModelCreationUtil(self.configuration_file_location,
                                                username=self.user_id,
                                                password=None,
                                                gateway_id=self.gateway_conf.GATEWAY_ID,
                                                access_token=access_token)

        grp_id = api_util.get_group_resource_profile_id(self.experiment_conf.GROUP_RESOURCE_PROFILE_NAME)
        app_id = api_util.get_execution_id(application_name)
        storage_id = api_util.get_storage_resource_id(self.experiment_conf.STORAGE_RESOURCE_HOST)
        resource_host_id = api_util.get_resource_host_id(computation_resource_name)

        experiment = data_model_util.get_experiment_data_model_for_single_application(
            project_name=self.experiment_conf.PROJECT_NAME,
            application_name=application_name,
            experiment_name=experiment_name,
            description=experiment_name)

        sftp_connector = SFTPConnector(host=self.experiment_conf.STORAGE_RESOURCE_HOST,
                                       port=self.experiment_conf.SFTP_PORT,
                                       username=self.user_id,
                                       password=access_token)

        path_suffix = sftp_connector.upload_files(local_input_path,
                                                  self.experiment_conf.PROJECT_NAME,
                                                  experiment.experimentName)


        logger.info("Input files uploaded to %s", path_suffix)

        path = self.gateway_conf.GATEWAY_DATA_STORE_DIR + path_suffix

        queue_name = queue_name if queue_name is not None else self.experiment_conf.QUEUE_NAME

        node_count = node_count if node_count is not None else self.experiment_conf.NODE_COUNT

        cpu_count = cpu_count if cpu_count is not None else self.experiment_conf.TOTAL_CPU_COUNT

        walltime = walltime if walltime is not None else self.experiment_conf.WALL_TIME_LIMIT

        logger.info("configuring inputs ......")
        experiment = data_model_util.configure_computation_resource_scheduling(experiment_model=experiment,
                                                                                      computation_resource_name=computation_resource_name,
                                                                                      group_resource_profile_name=self.experiment_conf.GROUP_RESOURCE_PROFILE_NAME,
                                                                                      storageId=storage_id,
                                                                                      node_count=int(node_count),
                                                                                      total_cpu_count=int(cpu_count),
                                                                                      wall_time_limit=int(walltime),
                                                                                      queue_name=queue_name,
                                                                                      experiment_dir_path=path,
                                                                                      auto_schedule=auto_schedule)


        input_files = []
        if (len(input_file_mapping.keys()) > 0):
            new_file_mapping = {}
            for key in input_file_mapping.keys():
                if type(input_file_mapping[key]) == list:
                    data_uris = []
                    for x in input_file_mapping[key]:
                        data_uri = data_model_util.register_input_file(file_identifier=x,
                                                                              storage_name=self.experiment_conf.STORAGE_RESOURCE_HOST,
                                                                              storageId=storage_id,
                                                                              input_file_name=x,
                                                                              uploaded_storage_path=path)
                        data_uris.append(data_uri)
                    new_file_mapping[key] = data_uris
                else:
                    x = input_file_mapping[key]
                    data_uri = data_model_util.register_input_file(file_identifier=x,
                                                                          storage_name=self.experiment_conf.STORAGE_RESOURCE_HOST,
                                                                          storageId=storage_id,
                                                                          input_file_name=x,
                                                                          uploaded_storage_path=path)
                    new_file_mapping[key] = data_uri
            experiment = data_model_util.configure_input_and_outputs(experiment, input_files=None,
                                                                            application_name=self.experiment_conf.APPLICATION_NAME,
                                                                            file_mapping=new_file_mapping)

            print(new_file_mapping)
        else:
            for x in os.listdir(local_input_path):
                if os.path.isfile(local_input_path + '/' + x):
                    input_files.append(x)

            if len(input_files) > 0:
                data_uris = []
                for x in input_files:
                    data_uri = data_model_util.register_input_file(file_identifier=x,
                                                                          storage_name=self.experiment_conf.STORAGE_RESOURCE_HOST,
                                                                          storageId=storage_id,
                                                                          input_file_name=x,
                                                                          uploaded_storage_path=path)
                    data_uris.append(data_uri)
                experiment = data_model_util.configure_input_and_outputs(experiment, input_files=data_uris,
                                                                                application_name=self.experiment_conf.APPLICATION_NAME)
            else:
                inputs = self.api_server_client.get_application_inputs(airavata_token, app_id)
                experiment.experimentInputs = inputs

        outputs = self.api_server_client.get_application_outputs(airavata_token, app_id)

        experiment.experimentOutputs = outputs

        # create experiment
        ex_id = self.api_server_client.create_experiment(airavata_token, self.gateway_conf.GATEWAY_ID, experiment)

        # launch experiment
        self.api_server_client.launch_experiment(airavata_token, ex_id, self.gateway_conf.GATEWAY_ID)


        return ex_id
        #if not grp_id:



