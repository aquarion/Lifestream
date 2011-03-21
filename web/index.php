<?PHP
require("library.php");

$dbcxn = getDatabase();

header('Content-type: text/html; charset=UTF-8') ;

define("PAGEID", "aqlifestream_".md5($_SERVER['REQUEST_URI'].json_encode($_POST)));

$memcached = false;

if(isset($config['memcache']) && ! isset($_GET['skipcache'])) {
	$memcached =  memcache_connect($config['memcache']['host'], $config['memcache']['port']);
}

if($memcached){
	if($result = $memcached->get(PAGEID)){
		#error_log("From Memcache ".PAGEID);
		echo $result;
		exit;
	}
}

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


while($row = mysql_fetch_assoc($results)){

  $row = process_lifestream_item($row);

	if(isset($out[count($out)-1]) && $out[count($out)-1]['content'] == $row['content']){
		
	} else {
			$out[] = $row;
	}

}

$format = false;
if (isset($_REQUEST['format'])){
	$format = $_REQUEST['format'];
}

switch ($format){
	case "html":
		$output = "";
		foreach($out as $row){
			$output .= "<div class=\"lifestream ".$row['type']."\" id=\"".$row['id']."\">
			<a href=\"".$row['url']."\">
				<img src='".$row['icon']."'/ height=\"16px\" alt=\"".$row['source']."\">
			</a>
			<span>".$row['content']."</span>
			<span class=\"moreinfo\">".$row['source']."<br/><a class=\"nicetime\" href=\"".$row['url']."\">".$row['nicetime']." ago</a></span></div>\n";
		}
		break;
	
	default:
		$output = json_encode($out);
}

echo $output;

if($memcached){
	$memcached->set(PAGEID, $output, 0, 60);
	#error_log("Memcached ".PAGEID);
}
