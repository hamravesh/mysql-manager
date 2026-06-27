Feature: add replica to cluster
  add one replica to current cluster and check its state

  Scenario: start first mysql and add second replica
    Given setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And init mysql cluster spec
    And setup haproxy with name hap1 with env ETCD_HOST=http://etcd:2379 ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And setup haproxy with name hap2 with env ETCD_HOST=http://etcd:2379 ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And sleep 30 seconds
    Then cluster status must be
    """
    source=up
    replica=down

    """
    When execute mysql query with user: hamadmin, password: password, host: hap1 and port: 3306 query: use hamdb; CREATE TABLE t1 (c1 INT PRIMARY KEY, c2 TEXT NOT NULL);INSERT INTO t1 VALUES (1, 'Luis');
    And execute mysql query with user: root, password: root, host: mysql-s1 and port: 3306 query: flush binary logs;
    And execute mysql query with user: root, password: root, host: mysql-s1 and port: 3306 query: purge binary logs before now();
    And execute mysql query with user: hamadmin, password: password, host: hap2 and port: 3306 query: use hamdb; INSERT INTO hamdb.t1 VALUES (2, 'Hassan');
    And execute mysql query with user: root, password: root, host: mysql-s1 and port: 3306 query: flush binary logs;
    Given sleep 30 seconds
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
    Given setup default mysql with server_id 2
	  And add mysql to cluster with host: mysql-s2 and name: s2 and user: root and password: root
	  And sleep 50 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
    Then logs of mm must contain
    """
    Restart server failed (mysqld is not managed by supervisor process)
    """
    And replication should be running on mysql with server_id 2
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">1</field>
      </row>
    </resultset>
    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap2 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">1</field>
      </row>
    </resultset>
    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap1 and port: 3307 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">2</field>
      </row>
    </resultset>
    """
    Then result of query: "select @@global.server_id;" with user: hamadmin and password: password on host: hap2 and port: 3307 should be
    """
    <?xml version="1.0"?>

    <resultset statement="select @@global.server_id" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <row>
	    <field name="@@global.server_id">2</field>
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

  Scenario: start with two mysqls and add source again
    Given setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1
    And setup default mysql with server_id 2
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

