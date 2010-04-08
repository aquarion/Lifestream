<?PHP
require("library.php");
require("conn.php");

$dbcxn = mysql_connect(DBHOST, DBUSER, DBPASS);
mysql_select_db(DBNAME, $dbcxn);
header('Content-type: text/html; charset=UTF-8') ;

function escape_string($string){
	global $dbcxn;
	return mysql_real_escape_string($string, $dbcxn);
}

$filterquery = "";
if(isset($_REQUEST['filter'])){
	$filters = explode("/",$_REQUEST['filter']);

	$filterplus = array();
	$filterminus = array();

	foreach($filters as $filter){
		if($filter[0] == "-"){
			$filterminus[] = escape_string(substr($filter, 1));
		} else {
			$filterplus[] = escape_string($filter);
		}
	}

	if (count($filterplus) > 0 && count($filterminus) > 0){
		$filterquery .= ' and ( type not in("' . implode('", "', $filterminus).'")';
		$filterquery .= ' and type in("' . implode('", "', $filterplus).'"))';
		
	} elseif (count($filterminus)){
		$filterquery .= ' and (type not in("' . implode('", "', $filterminus).'"))';
	} else {
		$filterquery .= ' and (type in("' . implode('", "', $filterplus).'"))';
	}

}

$q = "select *, unix_timestamp(date_created) as epoch from lifestream where substring(title, 1, 1) != \"@\" and title not like \"#ebz%\" $filterquery order by date_created desc limit 10";
$results = mysql_query($q) or die(mysql_error());

$out = array();

function twitterFormat($text){
	

	$text = nl2br(ereg_replace("[[:alpha:]]+://[^<>[:space:]]+[[:alnum:]/]","<a href=\"\\0\">\\0</a>", $text));
	$text = preg_replace("#@(\w*)?#","<a href=\"http://www.twitter.com/\\1\">@\\1</a>", $text);
	
	$text = preg_replace("/#(\w*)/", "<a href=\"http://twitter.com/#search?q=%23\\1\">#\\1</a>", $text);
	
	$text = preg_replace("#^Aquarion: #", "", $text);

	$text = preg_replace("#http://raptr.com/Aquarion#", "", $text);
	$text = preg_replace("#^Xbox Live: #", "", $text);
	$text = preg_replace("# \(Xbox Live Nation\)$#", "", $text);
	
	return $text;
	
}

while($row = mysql_fetch_assoc($results)){

	$text = $row['title'];
	$row['originaltext'] = $row['title'];

	
	$row['content'] = twitterFormat($text);
	
	if(!$row['source']){
		$row['source'] = $row['type'];
	}

	switch ($row['type']) {
		
	case "lastfm":
		$icon = "http://imperial.istic.net/static/icons/silk/music.png";
		break;
		
	case "gaming":
		$icon = "http://imperial.istic.net/static/icons/silk/joystick.png";
		if ($row['source'] == "Champions Online"){
			$icon = "http://imperial.istic.net/static/icons/ChampionsOnline.png";
			$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "Raptr" && preg_match('#Champions Online! #', $text)){
			$row['content'] .= "#";
			continue 2;
		} elseif ($row['source'] == "XLN Live Integration"){
			$icon = "http://imperial.istic.net/static/icons/silk/controller.png";
			$row['url'] = "http://live.xbox.com/en-GB/profile/profile.aspx?pp=0&GamerTag=Jascain";
		}
		break;

	case "steam":
		$icon = "http://imperial.istic.net/static/icons/steam.png";
		$row['url'] = "http://steamcommunity.com/id/aquarion/";
		break;

	case "apps":
	
		if(preg_match("#^I favorited a YouTube video#", $row['content'])){
			$icon = "http://imperial.istic.net/static/icons/silk/film_add.png";
			$match = preg_match("#I favorited a YouTube video -- (.*?) (http.*)#", $row['originaltext'], $matches);
			
			$row['content'] = sprintf('<a href="%s">%s</a>', $matches[2], $matches[1]);
			$row['source'] = "YouTube";
				
			break;
		}
	
	case "twitter":
		$icon = "http://imperial.istic.net/static/icons/twitter/squared-shiny-16x16/twitter-02.png";
		if ($row['source'] == "Steepster"){
			$icon = "http://imperial.istic.net/static/icons/silk/cup.png";
			$row['content'] = preg_replace("/#\w*/", "", $row['originaltext']);
			preg_match("#(http://\S*)#", $row['content'], $matches);
			
			$row['url'] = $matches[1];
			
			$row['content'] = preg_replace("#: http://\S*#", "", $row['content']);
			
			#$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "foursquare"){
			$icon = "http://imperial.istic.net/static/icons/silk/map_magnify.png";
			$row['content'] = preg_replace("/#\w*/", "", $row['originaltext']);
			preg_match("#(http://\S*)#", $row['content'], $matches);
			
			$row['url'] = $matches[1];
			
			$row['content'] = preg_replace("#http://\S*#", "", $row['content']);
			
			$row['content'] = twitterFormat($row['content']);
			
			#$row['url'] = "http://www.champions-online.com/character_profiles/user_characters/Jascain";
		} elseif ($row['source'] == "web"){
			$row['source'] = "Twitter";
		}
		break; 

	case "flickr":
		$icon = "http://imperial.istic.net/static/icons/silk/picture.png";
		$row['content'] = sprintf('<a href="%s">%s</a>', $row['url'], $row['content']);
		break;

	default:
		$icon = "http://imperial.istic.net/static/icons/silk/asterisk_orange.png";

	}

	if($row['image']){
		$icon = $row['image'];
	} 

	$row['icon'] = $icon;
	$row['nicetime'] = nicetime($row['epoch']);

	$row['id'] = md5($row['systemid']);

	$out[] = $row;

	#echo "<div><img src='$icon'/ height=\"16px\"><a href=\"".$row['url']."\">".$row['title']."</a></div>\n";

}

$format = false;
if (isset($_REQUEST['format'])){
	$format = $_REQUEST['format'];
}

switch ($format){
	case "html":
		foreach($out as $row){
			echo "<div class=\"lifestream ".$row['type']."\" id=\"".$row['id']."\">
			<a href=\"".$row['url']."\">
				<img src='".$row['icon']."'/ height=\"16px\" alt=\"".$row['source']."\">
			</a>
			<span>".$row['content']."</span>
			<span class=\"moreinfo\">".$row['source']."<br/><a class=\"nicetime\" href=\"".$row['url']."\">".$row['nicetime']." ago</a></span></div>\n";
		}
		break;
	
	default:
		echo json_encode($out);
}
