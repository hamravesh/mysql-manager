Feature: Password rotation
  Test password rotation functionality for replication, exporter, nonpriv, and root users

  Background:
    Given setup etcd with name etcd and image: quay.hamdocker.ir/coreos/etcd:v3.5.9-amd64
    And setup user root with password: password for etcd
    And setup user mm for etcd with password: password access to path mm/cluster1/
    And setup default mysql with server_id 1
    And setup default mysql with server_id 2
    And setup mysql_manager with name mm with env ETCD_HOST=etcd ETCD_USERNAME=mm ETCD_PASSWORD=password ETCD_PREFIX=mm/cluster1/
    And init mysql cluster spec
    And sleep 30 seconds


  Scenario: Rotate replication password
    When execute password rotation command: python cli/mysql-cli.py rotate-passwords --repl new_repl_password
    And sleep 10 seconds
    Then user replica with password new_repl_password should be able to connect to source
    Then user replica with password new_repl_password should be able to connect to replica

    Then user root with password root should be able to connect to source
    Then user root with password root should be able to connect to replica
    Then user replica with password password should not be able to connect to source
    And replication should be working with new replica password. check with root root password


  Scenario: Rotate multiple passwords
    When execute password rotation command: python cli/mysql-cli.py rotate-passwords --repl new_repl --exporter new_exp --nonpriv new_np --root new_root
    And sleep 10 seconds
    Then user replica with password new_repl should be able to connect to source
    Then user exporter with password new_exp should be able to connect to source
    Then user hamadmin with password new_np should be able to connect to source
    

    Then user replica with password new_repl should be able to connect to remote
    Then user exporter with password new_exp should be able to connect to remote
    Then user hamadmin with password new_np should be able to connect to remote

    Then user root with password new_root should be able to connect to source
    Then user root with password new_root should be able to connect to replica

    Then user replica with password password should not be able to connect to source
    Then user exporter with password exporter should not be able to connect to source
    Then user hamadmin with password password should not be able to connect to source


    Then user root with password root should not be able to connect to source
    Then user root with password root should not be able to connect to replica


    Then user root with password new_root should be able to connect to source
    Then user root with password new_root should be able to connect to replica


    And replication should be working with new replica password. check with new_root root password

