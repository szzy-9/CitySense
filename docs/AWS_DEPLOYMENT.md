# CitySense AWS Connection and Deployment Plan

## Status and scope

CitySense is **partially configured but not proven deployed**. The repository has the local files needed for a basic Elastic Beanstalk deployment, but it has no AWS account details, resource identifiers, deployment URL, or verified RDS connection.

This guide is a plan for the developer to follow. No AWS resource was created or changed during the repository review. AWS resources can create ongoing charges, so create a budget alert first and check current AWS pricing.

The recommended first production architecture is one monolithic web deployment:

```text
User browser
    -> HTTPS Application Load Balancer managed by Elastic Beanstalk
    -> Flask/Gunicorn application
       -> serves the built Vue/Leaflet files
       -> serves /api routes
       -> connects to private PostgreSQL on Amazon RDS
       -> calls OpenRouteService and City of Melbourne APIs
    -> application and proxy logs stream to CloudWatch Logs
```

This keeps the Vue site and Flask API on one origin. It does not require Docker, Kubernetes, Lambda, API Gateway, or microservices.

The examples use the Sydney region. Replace `AWS_REGION` with the region you choose and keep all connected resources in that same region and VPC.

## 1. Create the minimum AWS resources

Create or confirm the following resources:

1. An AWS Budget alert.
2. One VPC. The default VPC is acceptable for an MVP if its networking is understood.
3. One external Amazon RDS for PostgreSQL database.
4. One RDS security group that accepts PostgreSQL only from the application instances.
5. One Elastic Beanstalk application and load-balanced Python environment.
6. An Elastic Beanstalk service role and EC2 instance profile with only the permissions required by the platform, CloudWatch Logs, and selected secrets.
7. Secrets Manager secrets or encrypted Parameter Store values for `RDS_PASSWORD` and `OPENROUTESERVICE_API_KEY`.
8. CloudWatch log groups created through Elastic Beanstalk log streaming.
9. For public HTTPS: a domain name/DNS record and an AWS Certificate Manager (ACM) certificate in the same region as the load balancer.

Keep RDS external to the Elastic Beanstalk environment. This prevents the database from being automatically tied to the web environment's lifecycle.

## 2. Create PostgreSQL on Amazon RDS

In the AWS Console, select `AWS_REGION`, then open **RDS -> Databases -> Create database**.

1. Choose **Standard create** and **PostgreSQL**.
2. Choose a currently supported PostgreSQL version.
3. Choose the lowest suitable development template and instance size. Confirm whether the account is eligible for a free-tier offer; do not assume it is free.
4. Set the DB instance identifier, for example `citysense-db`.
5. Set a master username. Generate a strong password and store it in Secrets Manager; never copy it into source code, README text, GitHub, or `.env.example`.
6. Set the initial database name to `citysense`.
7. Place the database in the same VPC as Elastic Beanstalk.
8. Set **Public access** to **No** for the final configuration.
9. Attach a dedicated security group such as `citysense-db-sg`.
10. For an MVP, use Single-AZ if the lower availability is acceptable. Enable automated backups and choose a short, deliberate retention period.
11. Create the database and record only the endpoint, port, username, and database name. Keep the password in the secret store.

The application runs `db.create_all()` during startup, so it can create the current `route_searches` table in an empty database. `backend/schema.sql` is also available for a controlled manual setup. A future production version should use migrations instead of relying on `create_all()`.

## 3. Configure the RDS security group

Do this after Elastic Beanstalk has created its EC2 instances and security group.

1. Open **EC2 -> Security Groups** and identify the security group attached to the Elastic Beanstalk EC2 instances. This is not the load balancer security group.
2. Open `citysense-db-sg`.
3. Add one inbound rule:
   - Type: PostgreSQL
   - Protocol: TCP
   - Port: `5432`
   - Source: the Elastic Beanstalk **instance** security group
4. Do not use `0.0.0.0/0` or `::/0` for PostgreSQL.
5. Confirm the application security group allows outbound traffic to RDS. The default outbound rule normally does.

AWS notes that referencing the automatically generated Elastic Beanstalk security group creates a dependency between the two groups. Before deleting an environment later, remove the RDS inbound reference. A dedicated application-to-database security group can remove that lifecycle problem later, but it is optional for the first MVP.

## 4. Let Flask read database settings from environment variables

`backend/config.py` already performs this work:

1. If `DATABASE_URL` is present, Flask-SQLAlchemy uses it.
2. Otherwise, if `RDS_HOSTNAME` is present, the code safely constructs the PostgreSQL URL from `RDS_HOSTNAME`, `RDS_PORT`, `RDS_USERNAME`, `RDS_PASSWORD`, `RDS_DB_NAME`, and `RDS_SSLMODE`.
3. Otherwise, local development uses `citysense.db` through SQLite.

The simplest AWS configuration is:

- Plain Elastic Beanstalk variables: `RDS_HOSTNAME`, `RDS_PORT`, `RDS_USERNAME`, `RDS_DB_NAME`, `RDS_SSLMODE`, `USE_LIVE_CITY_DATA`, `FLASK_DEBUG`, and `REQUEST_TIMEOUT_SECONDS`.
- Secrets Manager-backed variables: `RDS_PASSWORD` and `OPENROUTESERVICE_API_KEY`.

Use `RDS_SSLMODE=require` at minimum. For stricter certificate verification, configure the current Amazon RDS CA bundle and use `verify-full` after testing it.

On supported Elastic Beanstalk platform versions, open **Environment -> Configuration -> Updates, monitoring, and logging -> Runtime environment variables**. Choose **Secrets Manager** or **SSM Parameter Store** as the source and map each secret ARN to its environment variable name. Give the EC2 instance profile permission to read only those ARNs. Secret changes require an application-server restart or environment update before instances receive the new values.

## 5. Test the database connection safely

First confirm that the checker works with local SQLite:

```powershell
Set-Location D:\CitySense
.venv\Scripts\Activate.ps1
python -m backend.check_database
```

It prints only success/failure and the database type; it never prints the URL, host, user, or password.

A private RDS instance has no direct network route from a normal laptop. The safest first RDS test is from the deployed Elastic Beanstalk instance or through a properly configured VPN/SSM tunnel.

If a literal laptop-to-RDS test is required, use this short-lived method only:

1. Temporarily make the RDS instance publicly accessible.
2. Temporarily add one PostgreSQL inbound rule from the developer's current public IP ending in `/32`.
3. Put the RDS values in the ignored local `.env` file. Do not paste them into source code or commit them.
4. Run `python -m backend.check_database`.
5. Immediately remove the `/32` inbound rule and return RDS to **Public access: No**.

Never open PostgreSQL to the whole internet. If the test fails, check VPC routing, the exact current public IP, RDS status, security groups, port `5432`, database name, TLS mode, and credentials without printing the secret.

## 6. Build the Vue frontend

From Windows PowerShell:

```powershell
Set-Location D:\CitySense\frontend
pnpm install --frozen-lockfile
pnpm run build
Set-Location ..
```

The build creates `frontend/dist`. Keep `VITE_API_BASE_URL` blank for this combined deployment so the browser calls `/api` on the same HTTPS origin.

`frontend/dist` is ignored by Git, but it is intentionally not excluded by `.ebignore`, so the EB CLI includes the completed build in the source bundle. Build it again before every deployment.

## 7. Confirm Flask serves the Vue build

From the project root:

```powershell
.venv\Scripts\Activate.ps1
python -m backend.app
```

Check:

- `http://localhost:5000/` shows the built Vue page.
- `http://localhost:5000/api/health` returns a JSON status of `ok`.
- `http://localhost:5000/api/places` returns the six fixed places.

`backend/app.py` serves `frontend/dist/index.html` at `/` and hashed assets under `/assets`. The production `Procfile` starts Gunicorn through `application.py`.

## 8. Deploy the combined application to Elastic Beanstalk

Install and configure the AWS and EB command-line tools outside the project virtual environment as appropriate for the workstation. Use an IAM identity with limited deployment permissions.

```powershell
aws configure set region AWS_REGION
eb init
```

During `eb init`:

- Select `AWS_REGION`.
- Use an application name such as `citysense`.
- Choose a currently supported **Python 3.12 on 64-bit Amazon Linux 2023** platform branch.
- Do not enable SSH unless it is needed and secured.

Create a load-balanced environment with an Application Load Balancer so HTTPS can be terminated at the load balancer:

```powershell
eb create citysense-prod --elb-type application
```

This costs more than a single-instance environment. A `--single` environment is acceptable for a temporary HTTP-only classroom demonstration, but it has no load balancer and cannot use the recommended load-balancer HTTPS setup.

After environment creation:

1. Configure the environment variables and secret mappings from step 4.
2. Put Elastic Beanstalk and RDS in the same VPC.
3. Configure the RDS security-group rule from step 3.
4. Set the default process health-check path to `/api/health`.
5. Deploy the latest source bundle:

```powershell
eb deploy
eb status
eb open
```

Do not deploy until `frontend/dist` exists and the local checks pass.

## 9. Verify the secure Elastic Beanstalk-to-RDS connection

The secure path should be:

```text
Elastic Beanstalk EC2 instance security group
    -> TCP 5432
    -> RDS security group
    -> private PostgreSQL endpoint using TLS
```

Confirm:

- RDS is not publicly accessible.
- No RDS rule allows the whole internet.
- The EB instance role can read only the required secret ARNs.
- `FLASK_DEBUG=false`.
- `RDS_SSLMODE=require` or stricter.
- A route request succeeds and creates a row in `route_searches`.
- Logs do not contain credentials or connection URLs.

If the database is unavailable during a route request, the current API rolls back the transaction, logs a generic error, and returns HTTP `503` without exposing credentials.

## 10. Configure HTTPS

For a browser-trusted certificate, use a domain you control.

1. Request a public certificate in **AWS Certificate Manager** in the same region as the Elastic Beanstalk load balancer.
2. Add the domain names that will be used, then complete DNS validation.
3. Create a DNS alias/CNAME for the application domain that points to the Elastic Beanstalk environment/load balancer. Route 53 is convenient but not required.
4. In **Elastic Beanstalk -> Environment -> Configuration -> Load balancer**, add an HTTPS listener on port `443` and select the ACM certificate.
5. Forward decrypted traffic to the default HTTP process on the application instances.
6. After HTTPS works, configure port `80` to redirect to `443`, or disable the HTTP listener. Test the redirect after each environment configuration change.
7. Set `FRONTEND_ORIGIN` to the final HTTPS origin if cross-origin development access is still needed.

The application uses one origin in production, so there is no browser mixed-content or cross-origin requirement between Vue and Flask. Do not add a wildcard CORS origin.

## 11. Enable and view CloudWatch logs

In **Elastic Beanstalk -> Environment -> Configuration -> Updates, monitoring, and logging**:

1. Enable **Instance log streaming to CloudWatch Logs**.
2. Choose a deliberate retention period, such as 7 or 14 days for a small teaching project.
3. Decide whether logs should remain after the environment is terminated.
4. Apply the configuration.

Use **Elastic Beanstalk -> Logs** or **CloudWatch -> Log groups**. For the Python platform, useful streams include `web.stdout.log`, Nginx access/error logs, `eb-engine.log`, and `eb-hooks.log`.

CLI options include:

```powershell
eb logs --cloudwatch-logs enable
eb logs --all
```

The application now logs generic external-service fallback types and database write failures. It does not log API keys, database URLs, or JSON request bodies.

## 12. Test the deployed application

Run this checklist using the final HTTPS domain:

1. `/` loads Vue, CSS, JavaScript, and the OpenStreetMap tiles without browser console errors.
2. `/api/health` returns HTTP `200` and `{"service":"CitySense API","status":"ok"}`.
3. `/api/places` returns six locations.
4. Selecting two different locations returns two route cards and map lines.
5. The interface clearly reports whether route and pedestrian sources are live or fallback.
6. Identical locations produce a clear validation error.
7. A route search creates a PostgreSQL row; confirm through a controlled database query, not by exposing database access publicly.
8. HTTP redirects to HTTPS, and the certificate matches the domain.
9. CloudWatch receives application and proxy logs.
10. No secret appears in the browser bundle, page source, network response, Git files, or logs.

## Official AWS references

- [Deploying a Flask application to Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-flask.html)
- [Using the Elastic Beanstalk Python platform](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-container.html)
- [Using Elastic Beanstalk with Amazon RDS](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.RDS.html)
- [Fetching Secrets Manager and Parameter Store values into environment variables](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.secrets.env-vars.html)
- [Configuring HTTPS for Elastic Beanstalk](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/configuring-https.html)
- [Using Elastic Beanstalk with CloudWatch Logs](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.cloudwatchlogs.html)
- [Using SSL with RDS for PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)
