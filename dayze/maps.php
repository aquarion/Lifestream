<?php

require("../web/library.php");

getDatabase();
ORM::configure('logging', true);
ORM::configure('driver_options', array(PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8'));
$query = ORM::for_table('lifestream_locations');


$from = mktime(0,0,0, 1, 1, $split[0]);
$to   = strtotime("+1 year", $from) -1;
$query->where_gt("date_created", date("Y-m-d 00:00", $from));
$query->where_lt("date_created", date("Y-m-d 00:00", $to));

?><html>
<body>
  <div id="mapdiv"></div>
  <script src="/assets/js/OpenLayers.js"></script>
  <script>
    map = new OpenLayers.Map("mapdiv");
    map.addLayer(new OpenLayers.Layer.OSM());
 
    var lonLat = new OpenLayers.LonLat( -0.1279688 ,51.5077286 )
          .transform(
            new OpenLayers.Projection("EPSG:4326"), // transform from WGS 1984
            map.getProjectionObject() // to Spherical Mercator Projection
          );
 
    var zoom=16;
 
    var markers = new OpenLayers.Layer.Markers( "Markers" );
    map.addLayer(markers);
 
    markers.addMarker(new OpenLayers.Marker(lonLat));
 
    map.setCenter (lonLat, zoom);
  </script>
</body></html>