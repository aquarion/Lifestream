<?php

require("../web/library.php");

getDatabase();
ORM::configure('logging', true);
ORM::configure('driver_options', array(PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8'));
$query = ORM::for_table('lifestream_locations');


if(isset($_GET['year'])){
	$to   = mktime(23,59,59,12,31,intval($_GET['year']));
	$from = $to - A_YEAR*1;
} else {
	$to   = time();
	$from = $to - A_DAY * 30;
}

 
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
        $title = $row['title'].' - '.$row['timestamp'];
    } else {
        $title = $row['timestamp'];
    }
    
  if($key !== $previous){
    $newentry = array("lat" => $row['lat_vague'], "long" => $row['long_vague'], 'title' => $title, 'source' => $row['source']);
        if($row['icon']){
            $newentry['icon'] = $row['icon'];
        }
    $locations[] = $newentry;
  }
  
  $previous = $key;
}

$title = "Heatmap of locations". ( isset($_GET['year']) ? ' for '.$_GET['year'] : ' last 30 days' );

?><html>
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
  
   <title><?PHP echo $title ?></title>
<meta property="og:title" content="<?PHP echo $title ?>" />
<meta property="og:image" content="https://nicholasavenell.com/assets/map-icon.png">

    <style type="text/css">
      html { height: 100% }
      body { height: 100%; margin: 0; padding: 0 }
      #map-canvas { height: 100% }
	.leaflet-container {
	    background: rgb(2,50,54) !important;
	}


    </style>

<script type="text/javascript">

var locations = <?PHP print json_encode($locations) ?>;

</script>
  <script src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js"></script>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.1.0/dist/leaflet.css"  crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.1.0/dist/leaflet.js" crossorigin=""></script>

<script type="text/javascript" src="/assets/js/webgl-heatmap-master/webgl-heatmap.js"></script>
<script type="text/javascript" src="/assets/js/leaflet-webgl-heatmap-master/dist/leaflet-webgl-heatmap.min.js"></script>
<script type="text/javascript" src="https://stamen-maps.a.ssl.fastly.net/js/tile.stamen.js?v1.3.0"></script>

    <script type="text/javascript">

var defaultIcon = L.icon({
    iconUrl: 'https://nicholasavenell.com/assets/marker.png',
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

  //
  var sataliteMap = new L.tileLayer("https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiYXF1YXJpb24iLCJhIjoiQzRoeUpwZyJ9.gIhABGtR7UMR-LZUJGRW0A")
  //map.addLayer(sataliteMap);

  
  var metropolisMap = new L.tileLayer("https://api.mapbox.com/styles/v1/aquarion/cjbj6ztf70vro2sl4y09909bg/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoiYXF1YXJpb24iLCJhIjoiQzRoeUpwZyJ9.gIhABGtR7UMR-LZUJGRW0A");
  map.addLayer(metropolisMap);

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

    weight = .2 

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
          weight = .4
          foursquareMarkers.push(marker)
    // } else if (point['source'] !== "openpaths") {
    //       marker = new L.Marker(markerpos, {
    //         icon: defaultIcon,
    //         draggable:false,
    //         title: point['title']
    //       });
    //       marker.addTo(map)
    //     console.log(point)

    }

    
    //heatmapData.push({'lat': point['lat'], 'lon': point['long'], 'value': 0.4});
    heatmapData.push([point['lat'], point['long'], weight ]);


  }

  foursquareLayer = new L.featureGroup(foursquareMarkers)
  heatmap.setData(heatmapData)


  map.addLayer(heatmap);
  //map.addLayer(foursquareLayer);


   
  var overlays = {
      //"Marker": marker,
      "Roads": labelsLayer,
      "Heatmap": heatmap,
      "Foursquare": foursquareLayer
  };
  var baseLayers = {
      //"Marker": marker,
      "Metropolis": metropolisMap,
      "Satellite-9": sataliteMap,
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
