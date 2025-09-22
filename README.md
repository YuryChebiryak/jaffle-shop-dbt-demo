This repository explores how data contracts can be defined and enforced for the classic Jaffle Shop dbt demo.

Medium article with the original setup of dbt with a local postgres:
[Medium Link](https://medium.com/@snhou/running-the-jaffle-shop-dbt-project-in-seconds-47bf72363744)

Our setup is different from the original repo in that we: 1. use `uv` instead of `pip` and 2. use `podman` instead of `docker`.

## Prerequisites
1. git
2. Python 3.9 or higher
3. Docker Desktop


## Setup environment

1. Clone this repository
```bash
git clone https://github.com/YuryChebiryak/jaffle-shop-dbt-demo.git
```
2. Change into the `jaffle_shop` directory
```bash
cd jaffle-shop-dbt-demo
``` 

3. Install virtual environment
``` bash
python3 -m venv venv
```

4. Enter into venv
```bash
source venv/bin/activate
```

5. Update pip
```bash
python3 -m pip install --upgrade pip
```

6. Install uv
```bash
pip install uv
```

6. Install dependencies
```bash
uv pip install -r requirements.txt
```

7. Install podman, initialize it and start it

```bash
brew install podman
podman machine init
podman machine start
```

7. Run Podman
```bash
podman compose build
```
```bash
podman compose up -d
```

## Running this project

1. Set up a `profiles.yml` called `jaffle_shop` to connect to a data warehouse

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: dbt
      password: dbt
      port: 5432
      dbname: dbt
      schema: jaffle-shop-classic
      threads: 4
```

2. Ensure your profile is setup correctly from the command line:
```bash
dbt debug
```
* it will generate a `.user.yml` file
 
3. Load the CSVs with the demo data set. This materializes the CSVs as tables in your target schema. Note that a typical dbt project **does not require this step** since dbt assumes your raw data is already in your warehouse.
```bash
dbt seed
```

4. Run the models:
```bash
dbt run
```


5. Test the output of the models:
```bash
dbt test
```

6. Generate documentation for the project:
```bash
dbt docs generate
```

7. View the documentation for the project:
```bash
dbt docs serve
```
