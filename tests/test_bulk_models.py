import os
from utils_test import delete_experiments, delete_models, mk_test_object_name, list_experiments
from compare_utils import compare_runs

from mlflow_export_import.model.export_model import ModelExporter
from mlflow_export_import.bulk.export_models import export_models
from mlflow_export_import.bulk.import_models import import_all
from mlflow_export_import.bulk import bulk_utils
from test_bulk_experiments import create_test_experiment
from init_tests import mlflow_server

# == Setup

notebook_formats = "SOURCE,DBC"
model_suffix = "Original"
num_models = 1
num_experiments = 1
exporter = ModelExporter() 

def _init(client):
    delete_models(client)
    delete_experiments(client)

# == Export/import registered model tests

def _rename_model_name(model_name):
    return f"{model_name}_{model_suffix}"

def _create_model(client):
    exp = create_test_experiment(client, num_experiments)
    model_name = mk_test_object_name()
    model = client.create_registered_model(model_name)
    for run in client.search_runs([exp.experiment_id]):
        source = f"{run.info.artifact_uri}/model"
        client.create_model_version(model_name, source, run.info.run_id)
    return model.name

def _run_test(mlflow_server, compare_func, import_metadata_tags=False, use_threads=False):
    _init(mlflow_server.client)
    model_names = [ _create_model(mlflow_server.client) for j in range(0,num_models) ]
    export_models(model_names, mlflow_server.output_dir, notebook_formats, stages="None", export_all_runs=False, use_threads=False)
    for model_name in model_names:
        mlflow_server.client.rename_registered_model(model_name,_rename_model_name(model_name))
    exps = list_experiments(mlflow_server.client) 
    for exp in exps:
        mlflow_server.client.rename_experiment(exp.experiment_id, f"{exp.name}_{model_suffix}")

    import_all(mlflow_server.output_dir,
        delete_model=False,
        use_src_user_id=False,
        import_metadata_tags=import_metadata_tags,
        verbose=False,
        use_threads=use_threads)

    test_dir = os.path.join(mlflow_server.output_dir,"test_compare_runs")

    exp_ids = [ exp.experiment_id for exp in exps ]
    models2 = mlflow_server.client.search_registered_models("name like 'model_%'")
    for model2 in models2:
        model2 = mlflow_server.client.get_registered_model(model2.name)
        versions = mlflow_server.client.get_latest_versions(model2.name)
        for vr in versions:
            run2 = mlflow_server.client.get_run(vr.run_id)
            tag = run2.data.tags["my_uuid"]
            filter = f"tags.my_uuid = '{tag}'"
            run1 = mlflow_server.client.search_runs(exp_ids, filter)[0]
            tdir = os.path.join(test_dir,run2.info.run_id)
            os.makedirs(tdir)
            assert run1.info.run_id != run2.info.run_id
            compare_func(mlflow_server.client, tdir, run1, run2)

def test_basic(mlflow_server):
    _run_test(mlflow_server, compare_runs)

def test_exp_basic_threads(mlflow_server):
    _run_test(mlflow_server, compare_runs, use_threads=True)

def test_exp_import_metadata_tags(mlflow_server):
    _run_test(mlflow_server, compare_runs, import_metadata_tags=True)


def test_get_model_names_from_comma_delimited_string(mlflow_server):
    model_names = bulk_utils.get_model_names("model1,model2,model3")
    assert len(model_names) == 3

def test_get_model_names_from_all_string(mlflow_server):
    _init(mlflow_server.client)
    model_names1 = [ _create_model(mlflow_server.client) for j in range(0,3) ]
    model_names2 = bulk_utils.get_model_names("*")
    assert set(model_names1) == set(model_names2)
