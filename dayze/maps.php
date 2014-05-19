<?php

require("../web/library.php");

getDatabase();
ORM::configure('logging', true);
ORM::configure('driver_options', array(PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8'));
$query = ORM::for_table('lifestream_locations');


$from = time() - 60*60*24*3;
$to   = time();
  $query->where_gt("timestamp", date("Y-m-d 00:00", $from));
  $query->where_lt("timestamp", date("Y-m-d 00:00", $to));
$items = $query->find_array();


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


?><html>
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 100%; margin: 0; padding: 0 }
      #map-canvas { height: 100% }
    </style>

<script type="text/javascript">

var locations = <?PHP print json_encode($locations) ?>;

</script>
  <script src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js"></script>
    <script type="text/javascript"
      src="https://maps.googleapis.com/maps/api/js?key=AIzaSyBdHTYldEJBPKy0F4g8P1t653oKpPJtwyk&sensor=false">
    </script>
    <script type="text/javascript">


      function google_map(){

        console.log("Hello World");
        
  if (locations.length == 0){
    return;
  }
  
  var bounds = new google.maps.LatLngBounds();
  
  
  
  for(i=0;i < locations.length; i++){
    markerpos = new google.maps.LatLng(locations[i]['lat'], locations[i]['long']);
    bounds.extend(markerpos)    
    console.log(markerpos)
  }
  
  var myOptions = {
    center: new google.maps.LatLng(0, 0),
    zoom: 1,
   disableDefaultUI: true,
      scrollwheel: false,
      draggable: false,
      keyboardShortcuts: false,
    mapTypeId: google.maps.MapTypeId.ROADMAP
  };
  
  var map = new google.maps.Map(document.getElementById("mapcanvas"), myOptions);
    
  defaultimage = 'https://phenomsff.com/images/red.png';

  for(i=0;i < locations.length; i++){
    markerpos = new google.maps.LatLng(locations[i]['lat'], locations[i]['long']);
        
        if (locations[i]['icon']){
            image = locations[i]['icon'];
              marker = new google.maps.Marker({
                map:map,
                draggable:false,
                position: markerpos,
                //icon: image,
                title: locations[i]['title']
              });
        } else {
              marker = new google.maps.Marker({
                icon: defaultimage,
                map:map,
                draggable:false,
                animation: google.maps.Animation.DROP,
                position: markerpos,
                title: locations[i]['title']
              });

        }
        

    
   }
  
  map.fitBounds(bounds);
  // var listener = google.maps.event.addListener(map, "idle", function() { 
  //   if (map.getZoom() > 16) map.setZoom(16); 
  //   google.maps.event.removeListener(listener); 
  // });
      }

$( document ).ready(function() {
  google_map();
});
    </script>
  </head>
  <body>
    <div id="mapcanvas" style="height: 100%; width: 100%"/>
  </body>
</html>