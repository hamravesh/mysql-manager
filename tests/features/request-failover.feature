Feature: test failover
  setup 2 nodes, request failover first for replica and then for source. For source database, failover should be performed without any problems.

  Scenario: request failover
    Given setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1
    And setup default mysql with server_id 2
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And init mysql cluster spec
    And sleep 30 seconds
    # NOT EXISTING DATABASE
    And request failover for mysql with name: s3
    And sleep 30 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
    Then result of query: "show replica status;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show replica status" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></resultset>
    """
    # REPLICA DATABASE
    Given request failover for mysql with name: s2
    And sleep 30 seconds
    Then cluster status must be
    """
    source=up
    replica=up

    """
    Then result of query: "show replica status;" with user: root and password: root on host: mysql-s1 and port: 3306 should be
    """
    <?xml version="1.0"?>

    <resultset statement="show replica status" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"></resultset>
    """
    # FAILOVER SHOULD BE EXECUTED HERE
    Given request failover for mysql with name: s1
    And sleep 30 seconds
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
