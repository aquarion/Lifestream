<?PHP
require("../web/library.php");
header("Content-type: text/html; charset=utf-8");
mb_language('uni');
mb_internal_encoding('UTF-8');

$dbcxn = getDatabase();
mysql_set_charset('utf8', $dbcxn); 
mysql_query("SET NAMES 'utf8' COLLATE 'utf8_unicode_ci'", $dbcxn);

$dateformat = "l j<\s\u\p>S</\s\u\p> F Y";
$dateformat_txt = "l jS F Y";

define("AN_HOUR", 60*60 );
define("A_DAY", 60*60*24 );
define("A_MONTH", 60*60*24*30 );
define("A_YEAR", 60*60*24*364 );

$today = false;

$tidy_config = array(
       	'indent'         => true,
       	'output-xhtml'   => true,
       	'wrap'           => 200);
$tidy = new tidy;

if (isset($_GET['year']) && isset($_GET['month']) && isset($_GET['day'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $d = intval($_GET['day']);  
  
  $from = mktime(0,0,0,$m,$d,$y);
  $to = mktime(23,59,59,$m,$d,$y);
  
  $datetitle = date($dateformat, $from);
  
  $backwards       = "/".date("Y", $from-A_DAY)."/".date("m", $from-A_DAY)."/".date("d", $from-A_DAY);
  $backwards_title = date($dateformat_txt, $from-A_DAY);

  $onwards         = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY)."/".date("d", $from+A_DAY);
  $onwards_title   = date($dateformat_txt, $from+A_DAY);
  
  $up              = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY);
  $up_title        = date("F Y", $from+A_DAY);
    
  $noforwards = false;
  if ($to > time()){
    $noforwards = true;
  }
  
  if(date("Y-m-d", $from) == date("Y-m-d")){
    $today = true;
  }

  $annuallink = "/[YEAR]/".date("m", $from)."/".date("d", $from);  

  $from += 4*AN_HOUR;
  $to   += 4*AN_HOUR;

} elseif (isset($_GET['year']) && isset($_GET['month'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $from = mktime(0,0,0,$m,1,$y);
  $to = mktime(23,59,59,$m,date("t", $from),$y);
  
  $next = mktime(0,0,0,$m+1,1,$y);
  $prev = mktime(0,0,0,$m-1,1,$y);
  
  $backwards       = "/".date("Y", $prev)."/".date("m", $prev);
  $onwards         = "/".date("Y", $next)."/".date("m", $next);
  $onwards_title   = date("F Y", $next);
  $backwards_title = date("F Y", $prev);
  
  $dateformat = "F Y";
  
  
  $noforwards = false;
  
  if (date("Ym", $next) > date("Ym")){
    $noforwards = true;
  }
  
  $datetitle = date($dateformat, $from);
  $annuallink = "/[YEAR]/".date("m", $from);
  
} elseif (isset($_GET['year'])){
  $y = intval($_GET['year']);
  
  $from = mktime(0,0,0,1,1,$y);
  $to = mktime(23,59,59,12,31,$y);
  
  $next = mktime(0,0,0,1,1,$y+1);
  $prev = mktime(0,0,0,11,1,$y-1);
  
  $backwards       = "/".date("Y", $prev);
  $onwards         = "/".date("Y", $next);
  
  $onwards_title   = date("Y", $next);
  $backwards_title = date("Y", $prev);
  
  #$datetitle = date($dateformat, $from)." to ".date($dateformat, $to);
  
  $dateformat = "Y";
  $datetitle = date($dateformat, $from);
  
  $annuallink="/[YEAR]/";
    
  $noforwards = false;
  if (date("Y", $next) > date("Y")){
    $noforwards = true;
  }

  
} else {
  $from = mktime(0,0);
  $to = mktime(23,59,59);

  if (date("H") < 4){
	$from -= A_DAY;
	$to -= A_DAY;
  }
  
  $datetitle = date($dateformat, $from);
  
  $backwards   = "/".date("Y", $from-A_DAY)."/".date("m", $from-A_DAY)."/".date("d", $from-A_DAY);
  $onwards     = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY)."/".date("d", $from+A_DAY);
  
  $onwards_title = date($dateformat_txt, $from+A_DAY);
  $backwards_title = date($dateformat_txt, $from-A_DAY);
  
  $up              = "/".date("Y", $from)."/".date("m", $from);
  $up_title        = date("F Y", $from);
  
  $today = $noforwards = true;
  $annuallink = "/[YEAR]/".date("m", $from)."/".date("d", $from);  


  $from += 4*AN_HOUR;
  $to   += 4*AN_HOUR;
}


$q = sprintf("select *, unix_timestamp(date_created) as epoch from lifestream where date_created between '%s' and '%s' order by date_created", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));

$results = mysql_query($q) or die(mysql_error());

$structure = array();

$structure['things'] = array();

$music = array();

while ($row = mysql_fetch_assoc($results)){

  $class = "Other";
  $row = process_lifestream_item($row);
  
  $id = md5($row['title']);
  
  switch ($row['type']){
    case "gaming":
    case "steam":
      $class = "Games";
      break;
      
    case "lastfm":
      //continue 2; // this is broken :(
      $class = "Music";
      
      list($artist, $track) = explode(" – ", $row['title']);
      $id = md5($artist);
      if(strlen($artist) > 31){
        $artist = substr($artist, 0, 31);
      }
      
      if (!isset($music[$artist])){
        $music[$artist] = 1;
      } else {
        $music[$artist] += 1;
      }
      continue 2;
      break;
      
    case "code":
      $class = "Code";
      break;
      
    case "twitter":
      $class = "Twitter";
      if ($row['originaltext'][0] == "@"){
	continue 2;
      }
      break;
      
    case "tumblr":
      $class = "Tumblr";
      $row['content'] = $row['title'];
      $tidy = new tidy;
      $tidy->parseString($row['title'], $tidy_config, 'utf8');
      $tidy->cleanRepair();
      $row['content'] = $tidy;
      #continue 2;
      break;
      
    case "location":
    case "oyster":
      $class = "Location";
      $id = md5($row['title']+$row['epoch']);
      break;
    
  }
  
  if ($row['source'] == "foursquare"){
    $class= "Location";
  }
  
  $row['class'] = $class;
  
  $class = "things";
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  if (isset($structure[$class][$id])){
      if (!isset($structure[$class][$id]['subitems'])){
       $structure[$class][$id]['subitems'] = array();
      }
      $structure[$class][$id]['subitems'][] = $row['title'];
  } else {  
    $structure[$class][$id] = $row;
  }
}


$q = sprintf("select post_title, post_content, ID, unix_timestamp(post_date) as epoch from aqcom_wp_posts where post_status = 'publish' and post_date between '%s' and '%s' order by post_date", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));


$results = mysql_query($q) or die(mysql_error());

while ($row = mysql_fetch_assoc($results)){
  
  $class = "Blog";
  
  #$row['content'] = $row['post_title'];
  #$row['content'] = $row['post_title']." &mdash; ".substr($row['post_content'], 0,256).'[...]';
$tidy = new tidy;
      $tidy->parseString($row['post_title']." &mdash; ".substr($row['post_content'], 0,256), $tidy_config, 'utf8');
      $tidy->cleanRepair();
      $row['content'] = $tidy;
  $row['title'] = $row['post_title'];
  $row['url'] = "http://www.aquarionics.com/?p=".$row['ID'];
  $row['source'] = "Aquarionics";
  $row['icon'] = 'http://art.istic.net/iconography/aqcom/logo_64.png';
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  
  
  $row['class'] = $class;
  
  $class = "things";
  
  
  
  
  $structure[$class][md5($row['title'])] = $row;
  
}

function epochsort($a,$b){
	if ($a['epoch'] > $b['epoch']){
		return 1;
	} elseif ($b['epoch'] > $a['epoch']) {
		return -1;
	}
	return 0;
}

include("view.php");

?>