apiVersion: postgresql.cnpg.io/v1
kind: Database
metadata:
  name: test-preview-pr-__PR__
  namespace: postgres-test
spec:
  name: __DB_NAME__
  owner: app
  cluster:
    name: testdb
  databaseReclaimPolicy: delete
  ensure: present
