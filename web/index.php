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

$q = "select *, unix_timestamp(date_created) as epoch from lifestream where substring(title, 1, 1) != \"@\" $filterquery order by date_created desc limit 10";
$results = mysql_query($q) or die(mysql_error());

$out = array();

while($row = mysql_fetch_assoc($results)){


	$text = nl2br(ereg_replace("[[:alpha:]]+://[^<>[:space:]]+[[:alnum:]/]","<a href=\"\\0\">\\0</a>", $row['title']));
	$text = preg_replace("#@(\w*)?#","@<a href=\"http://www.twitter.com/\\1\">\\1</a>", $text);
	$text = preg_replace("#^Aquarion: #", "", $text);

	$text = preg_replace("#^Xbox Live: #", "", $text);
	$text = preg_replace("# \(Xbox Live Nation\)$#", "", $text);
	
	$row['content'] = $text;

	switch ($row['type']) {
		
	case "lastfm":
		$icon = "http://imperial.istic.net/static/icons/silk/music.png";
		break;

	case "gaming":
		$icon = "http://imperial.istic.net/static/icons/silk/joystick.png";
		if ($row['source'] == "Champions Online"){
			$icon = "http://imperial.istic.net/static/icons/ChampionsOnline.png";
			$row['url'] = "http://www.champions-online.com/character_profiles/325750/view";
		} elseif ($row['source'] == "XLN Live Integration"){
			$icon = "http://imperial.istic.net/static/icons/silk/controller.png";
			$row['url'] = "http://live.xbox.com/en-GB/profile/profile.aspx?pp=0&GamerTag=Jascain";
		}
		break;

	case "steam":
		$icon = "http://imperial.istic.net/static/icons/steam.png";
		$row['url'] = "http://steamcommunity.com/id/aquarion/";
		break;

	case "twitter":
		$icon = "http://imperial.istic.net/static/icons/twitter/squared-shiny-16x16/twitter-02.png";
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
			<a class=\"nicetime\" href=\"".$row['url']."\">
				<img src='".$row['icon']."'/ height=\"16px\" alt=\"".$row['source']."\">
			</a>
			<span>".$row['content']."</span>
			<a class=\"nicetime\" href=\"".$row['url']."\">".$row['nicetime']."</a></div>\n";
		}
		break;
	
	default:
		echo json_encode($out);
}
