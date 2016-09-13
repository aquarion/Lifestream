<?php

require("../web/library.php");

getDatabase();
ORM::configure('logging', true);
ORM::configure('driver_options', array(PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8'));
$query = ORM::for_table('lifestream_locations');


$from = time() - A_MONTH;
$from = time() - A_YEAR*3;
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

<link rel="stylesheet" href="http://cdn.leafletjs.com/leaflet-0.7.3/leaflet.css" />
<script src="http://cdn.leafletjs.com/leaflet-0.7.3/leaflet.js"></script>
<script type="text/javascript" src="/assets/js/webgl-heatmap-leaflet/js/webgl-heatmap.js"></script>
<script type="text/javascript" src="/assets/js/webgl-heatmap-leaflet/js/webgl-heatmap-leaflet.js"></script>
<script type="text/javascript" src="http://maps.stamen.com/js/tile.stamen.js?v1.3.0"></script>

    <script type="text/javascript">

var defaultIcon = L.icon({
    iconUrl: 'https://phenomsff.com/images/red.png',
    iconSize: [16, 16],
});

var heatmapLayer = false


function locations_to_latlngs(){

  list = []

  for(i=0;i < locations.length; i++){
    markerpos = new L.LatLng(locations[i]['lat'], locations[i]['long']);
    markerpos['count'] = 2
    list.push(markerpos)
  }

  return list
}

function leaflet_map(){

  if (locations.length == 0){
    return;
  }

  // replace "toner" here with "terrain" or "watercolor"
  var map = new L.Map("mapcanvas", {
      center: new L.LatLng(locations[0]['lat'], locations[0]['long']),
      zoom: 12
  });

  var watercolorMap = new L.StamenTileLayer("watercolor");

  var tonerliteMap = new L.StamenTileLayer("toner-lite");
  var tonerMap = new L.StamenTileLayer("toner");
  map.addLayer(tonerliteMap);

  // var layer = new L.StamenTileLayer("toner-lines");
  // map.addLayer(layer);

  var labelsLayer = new L.StamenTileLayer("toner-labels");


  latlngs = locations_to_latlngs()
  var bounds = new L.LatLngBounds(latlngs);
  map.fitBounds(bounds);

  var heatmap = new L.webGLHeatmap({ 
    size : 5000,
    opacity : .7
  });


  heatmapData = []
  foursquareMarkers = []

  for(i=0;i < locations.length; i++){

    point = locations[i]

    markerpos = new L.LatLng(point['lat'], point['long']);
    

    if (point['icon']){
        image = point['icon'];
          marker = new L.Marker(markerpos, {
            map:map,
            draggable:false,
            title: point['title'],
            icon: L.icon({
                  iconUrl: point['icon'].replace('_64.png', '_bg_32.png'),
                  iconSize: [16, 16],
              })
          });
          foursquareMarkers.push(marker)
    } else {
          // marker = new L.Marker(markerpos, {
          //   icon: defaultIcon,
          //   draggable:false,
          //   title: point['title']
          // });
          // marker.addTo(map)

    }

    
    //heatmapData.push({'lat': point['lat'], 'lon': point['long'], 'value': 0.4});
    heatmapData.push([point['lat'], point['long'], .2]);


  }

  foursquareLayer = new L.featureGroup(foursquareMarkers)
  heatmap.setData(heatmapData)


  map.addLayer(heatmap);
  map.addLayer(foursquareLayer);


   
  var overlays = {
      //"Marker": marker,
      "Roads": labelsLayer,
      "Heatmap": heatmap,
      "Foursquare": foursquareLayer
  };
  var baseLayers = {
      //"Marker": marker,
      "Watercolor": watercolorMap,
      "Toner": tonerMap,
      "Toner Lite": tonerliteMap
  };
  L.control.layers(baseLayers, overlays).addTo(map);

}





$( document ).ready(function() {
  leaflet_map();
});
    </script>
  </head>
  <body>
    <div id="mapcanvas" style="height: 100%; width: 100%"/>
  </body>
</html>
