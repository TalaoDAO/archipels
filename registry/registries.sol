pragma solidity ^0.4.24;

contract registries {


    mapping (string => string) issuer_data;
    mapping (string => string) schema_data;

    // schema data , issuer data , issuer did and schema id are strings


    function get_issuer_data(string did) public view returns (string) {
        return issuer_data[did] ;
    }
    
    
    function set_issuer_data(string did, string json_issuer_data) public {
         issuer_data[did] = json_issuer_data;
    }


    function get_schema_data(string id) public view returns (string) {
        return schema_data[id] ;
    }
    
    
    function set_schema_data(string id, string json_schema_data) public {
         schema_data[id] = json_schema_data;
         
    }

}