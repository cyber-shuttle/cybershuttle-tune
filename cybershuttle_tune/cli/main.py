import typer
import cybershuttle_tune.parser as parser
import cybershuttle_tune.airavata_operator as operator
import cybershuttle_tune.sweeper as sweeper
import cybershuttle_tune.param_types as param_types

app = typer.Typer()


@app.command("parse")
def parse(file_path):
    print("Parsing File ", file_path)

if __name__ == "__main__":
    app()