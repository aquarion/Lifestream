<?php

require("../web/library.php");

getDatabase();
ORM::configure('logging', true);
ORM::configure('driver_options', array(PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8'));
$query = ORM::for_table('lifestream_locations');

$query->order_by_desc('timestamp');

#$items = array(get_object_vars($query->find_one()));

$items = array($query->find_one()->as_array());

$previous = "xxxx";
foreach ($items as $row){

  if (!$row['lat_vague']){
    $row['lat_vague'] = round($row['lat'], 2);
  }
  if (!$row['long_vague']){
    $row['long_vague'] = round($row['long'], 2);
  }
  
  $key = $row['lat_vague']."/".$row['long_vague'];
  
    if($row['title']){
        $title = $row['title'];
    } else {
        $title = $row['timestamp'];
    }
    
  if($key !== $previous){
    $newentry = array("lat" => $row['lat_vague'], "long" => $row['long_vague'], 'title' => $title);
        if($row['icon']){
            $newentry['icon'] = $row['icon'];
        }
    $locations[] = $newentry;
  }
  
  $previous = $key;
}

header("Content-Type: application/json");
print json_encode($locations);
