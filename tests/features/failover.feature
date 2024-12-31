Feature: test failover
  setup 2 nodes, kill master and check failover, after that restart previous master and it should join the cluster as a replica node

## TODO: check read only values on servers
  Scenario: start first mysql and add second replica
    Given setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup default mysql with server_id 2 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And setup haproxy with name hap1 with env ETCD_HOST=http://etcd:2379 ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And setup haproxy with name hap2 with env ETCD_HOST=http://etcd:2379 ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And init mysql cluster spec
    And sleep 30 seconds
    When execute mysql query with user: hamadmin, password: password, host: hap1 and port: 3306 query: use hamdb; CREATE TABLE t1 (c1 INT PRIMARY KEY, c2 TEXT NOT NULL);INSERT INTO t1 VALUES (1, 'Luis');
    Given stop mysql with server_id 1
    And sleep 30 seconds
    Then cluster status must be
    """
    source=up
    replica=down

    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">2</field>
      </row>
    </resultset>
    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">2</field>
      </row>
    </resultset>
    """
    Then result of query: "show replica status;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show replica status" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></resultset>
    """

    # Then result of query: "show master status;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    # """
    # """
    
    Then result of query: "select * from hamdb.t1;" with user: hamadmin and password: password on host: hap1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from hamdb.t1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="c1">1</field>
	    <field name="c2">Luis</field>
      </row>
    </resultset>
    """

    Then result of query: "select * from hamdb.t1;" with user: hamadmin and password: password on host: hap2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from hamdb.t1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="c1">1</field>
	    <field name="c2">Luis</field>
      </row>
    </resultset>
    """

    Then result of query: "SELECT user FROM mysql.user;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="SELECT user FROM mysql.user" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="user">exporter</field>
      </row>

      <row>
	    <field name="user">hamadmin</field>
      </row>

      <row>
	    <field name="user">replica</field>
      </row>

      <row>
	    <field name="user">root</field>
      </row>

      <row>
	    <field name="user">mysql.infoschema</field>
      </row>

      <row>
	    <field name="user">mysql.session</field>
      </row>

      <row>
	    <field name="user">mysql.sys</field>
      </row>

      <row>
	    <field name="user">root</field>
      </row>
    </resultset>
    """
    
    Then result of query: "show grants for hamadmin;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show grants for hamadmin" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="Grants for hamadmin@%">GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, SHUTDOWN, PROCESS, FILE, REFERENCES, INDEX, ALTER, SHOW DATABASES, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, REPLICATION SLAVE, REPLICATION CLIENT, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, TRIGGER, CREATE TABLESPACE, CREATE ROLE, DROP ROLE ON *.* TO `hamadmin`@`%` WITH GRANT OPTION</field>
      </row>
    
      <row>
	    <field name="Grants for hamadmin@%">GRANT APPLICATION_PASSWORD_ADMIN,AUDIT_ABORT_EXEMPT,AUDIT_ADMIN,AUTHENTICATION_POLICY_ADMIN,BACKUP_ADMIN,BINLOG_ADMIN,BINLOG_ENCRYPTION_ADMIN,CLONE_ADMIN,ENCRYPTION_KEY_ADMIN,FIREWALL_EXEMPT,FLUSH_OPTIMIZER_COSTS,FLUSH_STATUS,FLUSH_TABLES,FLUSH_USER_RESOURCES,GROUP_REPLICATION_ADMIN,GROUP_REPLICATION_STREAM,INNODB_REDO_LOG_ARCHIVE,INNODB_REDO_LOG_ENABLE,PASSWORDLESS_USER_ADMIN,PERSIST_RO_VARIABLES_ADMIN,REPLICATION_APPLIER,RESOURCE_GROUP_ADMIN,RESOURCE_GROUP_USER,ROLE_ADMIN,SENSITIVE_VARIABLES_OBSERVER,SERVICE_CONNECTION_ADMIN,SESSION_VARIABLES_ADMIN,SET_USER_ID,SHOW_ROUTINE,SYSTEM_USER,SYSTEM_VARIABLES_ADMIN,TABLE_ENCRYPTION_ADMIN,TELEMETRY_LOG_ADMIN,XA_RECOVER_ADMIN ON *.* TO `hamadmin`@`%` WITH GRANT OPTION</field>
      </row>
    </resultset>
    """

    Then result of query: "show databases;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show databases" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="Database">hamdb</field>
      </row>

      <row>
	    <field name="Database">information_schema</field>
      </row>

      <row>
	    <field name="Database">mysql</field>
      </row>

      <row>
	    <field name="Database">performance_schema</field>
      </row>

      <row>
	    <field name="Database">sys</field>
      </row>

      <row>
	    <field name="Database">test</field>
      </row>
    </resultset>
    """
    
    Given start mysql with server_id 1
    Given sleep 30 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">2</field>
      </row>
    </resultset>
    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">2</field>
      </row>
    </resultset>
    """
    When execute mysql query with user: hamadmin, password: password, host: hap2 and port: 3306 query: INSERT INTO hamdb.t1 VALUES (2, 'Hassan');
    Then result of query: "show replica status;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show replica status" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></resultset>
    """
    # Then result of query: "show master status;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    # """
    # """
    
    # Then result of query: "show replica status;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    # """
    # """
    
    # Then result of query: "show master status;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    # """
    # """
    
    Then result of query: "select * from hamdb.t1;" with user: hamadmin and password: password on host: hap1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from hamdb.t1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="c1">1</field>
	    <field name="c2">Luis</field>
      </row>
      <row>
	    <field name="c1">2</field>
	    <field name="c2">Hassan</field>
      </row>
    </resultset>
    """
    
    Then result of query: "select * from hamdb.t1;" with user: hamadmin and password: password on host: hap2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from hamdb.t1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="c1">1</field>
	    <field name="c2">Luis</field>
      </row>
      <row>
	    <field name="c1">2</field>
	    <field name="c2">Hassan</field>
      </row>
    </resultset>
    """
    
    Then result of query: "select * from hamdb.t1;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from hamdb.t1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="c1">1</field>
	    <field name="c2">Luis</field>
      </row>
      <row>
	    <field name="c1">2</field>
	    <field name="c2">Hassan</field>
      </row>
    </resultset>
    """
    
    Then result of query: "select * from hamdb.t1;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from hamdb.t1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="c1">1</field>
	    <field name="c2">Luis</field>
      </row>
      <row>
	    <field name="c1">2</field>
	    <field name="c2">Hassan</field>
      </row>
    </resultset>
    """

    Given restart mysql manager with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And sleep 20 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
    Then result of query: "show replica status;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show replica status" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></resultset>
    """
    # Then result of query: "show master status;" with user: root and password: root on host: mysql-s2 and port: 3306 should be
    # """
    # """
    
    # Then result of query: "show replica status;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    # """
    # """
    
    # Then result of query: "show master status;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    # """
    # """
  Scenario: increase the failinterval time and then do a failover
    Given setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup default mysql with server_id 2 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And init mysql cluster spec
    And change fail interval to 60 seconds
    And sleep 30 seconds
    """
    source=up
    replica=up

    """
    And stop mysql with server_id 1
    And sleep 45 seconds
    Then cluster status must be
    """
    source=down
    replica=replication_threads_stopped

    """
    Given sleep 35 seconds
    Then cluster status must be
    """
    source=up
    replica=down

    """
    Given start mysql with server_id 1
    And restart mysql manager with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And sleep 30 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
