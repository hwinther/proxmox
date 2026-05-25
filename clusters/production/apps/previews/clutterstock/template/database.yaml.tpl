apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: clutterstock-pr-__PR__
  namespace: postgres-test
spec:
  name: __DB_NAME__
  owner: app
  cluster:
    name: cluttertestdb
  reclaimPolicy: delete
  ensure: present
