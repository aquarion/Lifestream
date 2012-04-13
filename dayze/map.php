<?PHP

$q = sprintf("SELECT * FROM lifestream_locations where timestamp between '%s' and '%s' and (accuracy = 0 or accuracy < 50) group by date_format(timestamp, '%%Y%%m%%d%%H') order by id", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));

$locations = array();

$results = mysql_query($q) or die(mysql_error());

$previous = "xxxx";

while ($row = mysql_fetch_assoc($results)){

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


?>
<script type="text/javascript">

var locations = <?PHP print json_encode($locations) ?>;

</script>
 
<script type="text/javascript" src="http://maps.googleapis.com/maps/api/js?key=<?PHP echo lifestream_config("googleapi", "apikey")?>&sensor=false">
</script>

<script type="text/javascript">

var markers = []

initialize_google_map = function() {

	if (locations.length == 0){
		return;
	}
  
	var bounds = new google.maps.LatLngBounds();
  
	
  
	for(i=0;i < locations.length; i++){
		markerpos = new google.maps.LatLng(locations[i]['lat'], locations[i]['long']);
		bounds.extend(markerpos)		
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
	
	var map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
		
	for(i=0;i < locations.length; i++){
		markerpos = new google.maps.LatLng(locations[i]['lat'], locations[i]['long']);
        
        if (locations[i]['icon']){
            image = locations[i]['icon'];
              marker = new google.maps.Marker({
                map:map,
                draggable:false,
                position: markerpos,
                icon: image,
                title: locations[i]['title']
              });
        } else {
              marker = new google.maps.Marker({
                map:map,
                draggable:false,
                animation: google.maps.Animation.DROP,
                position: markerpos,
                title: locations[i]['title']
              });

        }
        

		
	}
	
	map.fitBounds(bounds);
	var listener = google.maps.event.addListener(map, "idle", function() { 
	  if (map.getZoom() > 16) map.setZoom(16); 
	  google.maps.event.removeListener(listener); 
	});
  }
  
</script>