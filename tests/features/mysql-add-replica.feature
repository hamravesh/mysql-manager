Feature: add replica to cluster
  add one replica to current cluster and check its state

  Scenario: start first mysql and add second replica
    Given setup default proxysql with name: proxysql and image: hub.hamdocker.ir/proxysql/proxysql:2.6.2
	  And setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
	  And init mysql cluster spec
    And sleep 30 seconds
    When execute mysql query with user: hamadmin, password: password, host: proxysql and port: 3306 query: use hamdb; CREATE TABLE t1 (c1 INT PRIMARY KEY, c2 TEXT NOT NULL);INSERT INTO t1 VALUES (1, 'Luis');
    And execute mysql query with user: root, password: root, host: mysql-s1 and port: 3306 query: flush binary logs;
    And execute mysql query with user: root, password: root, host: mysql-s1 and port: 3306 query: purge binary logs before now();
    And execute mysql query with user: hamadmin, password: password, host: proxysql and port: 3306 query: use hamdb; INSERT INTO hamdb.t1 VALUES (2, 'Hassan');
    And execute mysql query with user: root, password: root, host: mysql-s1 and port: 3306 query: flush binary logs;
    
    Then result of query: "select * from hamdb.t1;" with user: hamadmin and password: password on host: proxysql and port: 3306 should be
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
    Given setup default mysql with server_id 2 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
	  And add mysql to cluster with host: mysql-s2 and name: s2 and user: root and password: root
	  And sleep 50 seconds
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

    Then result of query: "select * from mysql_servers order by hostgroup_id, hostname;" with user: radmin and password: pwd on host: proxysql and port: 6032 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select * from mysql_servers order by hostgroup_id, hostname" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="hostgroup_id">0</field>
	    <field name="hostname">mysql-s1</field>
	    <field name="port">3306</field>
	    <field name="gtid_port">0</field>
	    <field name="status">ONLINE</field>
	    <field name="weight">1</field>
	    <field name="compression">0</field>
	    <field name="max_connections">1000</field>
	    <field name="max_replication_lag">0</field>
	    <field name="use_ssl">0</field>
	    <field name="max_latency_ms">0</field>
	    <field name="comment"></field>
      </row>

      <row>
	    <field name="hostgroup_id">1</field>
	    <field name="hostname">mysql-s1</field>
	    <field name="port">3306</field>
	    <field name="gtid_port">0</field>
	    <field name="status">ONLINE</field>
	    <field name="weight">1</field>
	    <field name="compression">0</field>
	    <field name="max_connections">1000</field>
	    <field name="max_replication_lag">0</field>
	    <field name="use_ssl">0</field>
	    <field name="max_latency_ms">0</field>
	    <field name="comment"></field>
      </row>

      <row>
	    <field name="hostgroup_id">1</field>
	    <field name="hostname">mysql-s2</field>
	    <field name="port">3306</field>
	    <field name="gtid_port">0</field>
	    <field name="status">ONLINE</field>
	    <field name="weight">1</field>
	    <field name="compression">0</field>
	    <field name="max_connections">1000</field>
	    <field name="max_replication_lag">0</field>
	    <field name="use_ssl">0</field>
	    <field name="max_latency_ms">0</field>
	    <field name="comment"></field>
      </row>
    </resultset>
    """


  Scenario: start with two mysqls and add source again
    Given setup default proxysql with name: proxysql and image: hub.hamdocker.ir/proxysql/proxysql:2.6.2 
    And setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup default mysql with server_id 2 and image: hub.hamdocker.ir/library/mysql:8.0.35-bullseye
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And init mysql cluster spec
    And sleep 40 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
    Given add mysql to cluster with host: mysql-s1 and name: s1 and user: root and password: root
    And restart mysql manager with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And sleep 10 seconds

    Then cluster status must be
    """
    source=up
    replica=up
    
    """