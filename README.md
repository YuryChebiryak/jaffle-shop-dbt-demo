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

7. Install dbt packages
```bash
dbt deps
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

## Apache Superset

Apache Superset is included in the docker-compose setup for data visualization and exploration.

### Accessing Superset

1. After running `podman compose up -d` or `docker-compose up -d`, Superset will be available at [http://localhost:8088](http://localhost:8088)

2. Default login credentials:
   - Username: `admin`
   - Password: `admin`

### Database Connection

The dbt database is automatically added as a data source during Superset initialization. You can immediately start creating charts and dashboards using the dbt-transformed data in the `jaffle-shop-classic` schema.

If you need to manually add or modify database connections:
1. Log in to Superset with the admin credentials
2. Go to **Data** > **Databases** in the top menu
3. Click **+ Database**
4. Select **PostgreSQL** as the database type
5. Enter the following connection details:
   - **Host**: `postgres`
   - **Port**: `5432`
   - **Database Name**: `dbt`
   - **Username**: `dbt`
   - **Password**: `dbt`
6. Click **Test Connection** to verify
7. Click **Add** to save the database

## Data-Driven Insights (DDI) Schema

The project includes a dedicated `ddi` schema for advanced analytics and insights models.

### Rolling 30-Day Orders Analysis

The `rolling_30_day_orders` model provides time-series analysis of completed orders with the following features:

- **Daily aggregations**: Total amount and order count per day
- **Rolling metrics**: 30-day rolling sums and averages
- **Trend analysis**: Last 50 data points for recent trend visualization
- **ANSI SQL compliance**: Portable across PostgreSQL, Snowflake, BigQuery, Redshift, etc.

#### Model Structure
- **order_date**: Date of orders (DATE)
- **total_amount**: Daily total payment amount (NUMERIC)
- **order_count**: Daily number of completed orders (INTEGER)
- **rolling_30_day_amount**: 30-day rolling sum of amounts (NUMERIC)
- **rolling_30_day_orders**: 30-day rolling sum of order counts (NUMERIC)
- **rolling_30_day_avg_daily**: 30-day rolling average daily amount (NUMERIC)

#### Data Contracts
The model enforces strict data quality contracts including:
- Not null constraints on all columns
- Value range validations
- Uniqueness constraints on dates
- Relationship validations

#### Usage in Superset
1. Navigate to **Data** > **Datasets**
2. Select the `dbt` database
3. Choose the `ddi.rolling_30_day_orders` table
4. Create charts using the rolling metrics for trend analysis
5. Use time-series charts to visualize order patterns over the 30-day windows
