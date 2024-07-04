# Prerequisites
1. git
2. Python 3.9 or higher
3. Docker Desktop


## Setup environment

1. Clone this repository
```bash
$ git clone https://github.com/snhou/jaffle-shop-dbt-demo.git
```
1. Change into the `jaffle_shop` directory
```bash
$ cd jaffle-shop-dbt-demo
``` 

1. Install virtual environment
``` bash
$ python3 -m venv venv
```

1. Enter into venv
```bash
$ source venv/bin/activate
```

1. Update pip
```bash
$ python3 -m pip install --upgrade pip
```

1. Install dependencies
```bash
$ python3 -m pip install -r requirements.txt
```

1. Open Docker Desktop and run docker-compose.yaml
```bash
$ docker compose build
```
```bash
$ docker compose up -d
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

1. Ensure your profile is setup correctly from the command line:
```bash
$ dbt debug
```
* it will generate a `.user.yml` file
 
1. Load the CSVs with the demo data set. This materializes the CSVs as tables in your target schema. Note that a typical dbt project **does not require this step** since dbt assumes your raw data is already in your warehouse.
```bash
$ dbt seed
```

1. Run the models:
```bash
$ dbt run
```


1. Test the output of the models:
```bash
$ dbt test
```

1. Generate documentation for the project:
```bash
$ dbt docs generate
```

1. View the documentation for the project:
```bash
$ dbt docs serve
```