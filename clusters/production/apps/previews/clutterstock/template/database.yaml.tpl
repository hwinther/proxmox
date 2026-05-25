apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: clutterstock-preview-pr-__PR__
  namespace: postgres-test
spec:
  name: __DB_NAME__
  owner: app
  cluster:
    name: cluttertestdb
  databaseReclaimPolicy: delete
  ensure: present
