// Provisions the AML data engineering stack:
// ADLS Gen2 (bronze/silver/gold), Data Factory, Databricks, Key Vault,
// Azure SQL Database (serving layer).
@description('Short project prefix used to name resources, e.g. amldataeng')
param projectPrefix string = 'amldataeng'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('SQL admin login for the serving database')
param sqlAdminLogin string = 'amladmin'

@secure()
@description('SQL admin password for the serving database')
param sqlAdminPassword string

@description('Region for the SQL server, if it needs to differ from the main location due to subscription restrictions')
param sqlLocation string = location

@description('Whether to deploy the Azure SQL serving database. Set to false if Microsoft.Sql provisioning is restricted on this subscription (common on new/trial subscriptions) — the gold Delta tables in ADLS can be queried directly (e.g. via Databricks SQL or Synapse serverless) without it.')
param deploySqlDatabase bool = true

var storageAccountName = toLower(take('${projectPrefix}st${uniqueString(resourceGroup().id)}', 24))
var dataFactoryName = '${projectPrefix}-adf-${uniqueString(resourceGroup().id)}'
var databricksName = '${projectPrefix}-dbx-${uniqueString(resourceGroup().id)}'
var keyVaultName = toLower('${projectPrefix}-kv-${take(uniqueString(resourceGroup().id), 8)}')
var sqlServerName = toLower('${projectPrefix}-sql-${uniqueString(resourceGroup().id)}')
var sqlDbName = '${projectPrefix}-servingdb'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true // enables ADLS Gen2 hierarchical namespace
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource bronzeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'bronze'
}

resource silverContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'silver'
}

resource goldContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'gold'
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    accessPolicies: []
    enableRbacAuthorization: true
  }
}

resource dataFactory 'Microsoft.DataFactory/factories@2018-06-01' = {
  name: dataFactoryName
  location: location
  identity: { type: 'SystemAssigned' }
}

resource databricks 'Microsoft.Databricks/workspaces@2023-02-01' = {
  name: databricksName
  location: location
  sku: { name: 'premium' }
  properties: {
    managedResourceGroupId: subscriptionResourceId(
      'Microsoft.Resources/resourceGroups',
      '${resourceGroup().name}-databricks-managed'
    )
  }
}

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = if (deploySqlDatabase) {
  name: sqlServerName
  location: sqlLocation
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    version: '12.0'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-05-01-preview' = if (deploySqlDatabase) {
  parent: sqlServer
  name: sqlDbName
  location: sqlLocation
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    maxSizeBytes: 2147483648
  }
}

resource sqlFirewallAllowAzure 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = if (deploySqlDatabase) {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output storageAccountName string = storage.name
output dataFactoryName string = dataFactory.name
output databricksWorkspaceUrl string = databricks.properties.workspaceUrl
output keyVaultName string = keyVault.name
output sqlServerFqdn string = deploySqlDatabase ? sqlServer.properties.fullyQualifiedDomainName : ''
output sqlDatabaseName string = deploySqlDatabase ? sqlDb.name : ''
