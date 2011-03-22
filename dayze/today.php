<?PHP
require("../web/library.php");
header('Content-type: text/html; charset=UTF-8') ;
$dbcxn = getDatabase();

$dateformat = "l j<\s\u\p>S</\s\u\p> F Y";
$dateformat_txt = "l jS F Y";

define("A_DAY", 60*60*24 );
define("A_MONTH", 60*60*24*30 );
define("A_YEAR", 60*60*24*364 );

if (isset($_GET['year']) && isset($_GET['month']) && isset($_GET['day'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $d = intval($_GET['day']);  
  
  $from = mktime(0,0,0,$m,$d,$y);
  $to = mktime(23,59,59,$m,$d,$y);
  
  $datetitle = date($dateformat, $from);
  
  $backwards       = "/".date("Y", $from-A_DAY)."/".date("m", $from-A_DAY)."/".date("d", $from-A_DAY);
  $onwards         = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY)."/".date("d", $from+A_DAY);
  $onwards_title   = date($dateformat_txt, $from+A_DAY);
  $backwards_title = date($dateformat_txt, $from-A_DAY);
  
  
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
  
  $datetitle = date($dateformat, $from);
  
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
  
} else {
  $from = mktime(0,0);
  $to = mktime(23,59,59);
  
  $datetitle = date($dateformat, $from);
  
  $backwards   = "/".date("Y", $from-A_DAY)."/".date("m", $from-A_DAY)."/".date("d", $from-A_DAY);
  $onwards     = "/".date("Y", $from+A_DAY)."/".date("m", $from+A_DAY)."/".date("d", $from+A_DAY);
  
  $onwards_title = date($dateformat_txt, $from+A_DAY);
  $backwards_title = date($dateformat_txt, $from-A_DAY);
}



$q = sprintf("select *, unix_timestamp(date_created) as epoch from lifestream where date_created between '%s' and '%s' order by date_created", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));

$results = mysql_query($q) or die(mysql_error());

$structure = array();

while ($row = mysql_fetch_assoc($results)){
  
  $class = "Other";
  $row = process_lifestream_item($row);
  
  switch ($row['type']){
    case "gaming":
    case "steam":
      $class = "Games";
      break;
      
    case "lastfm":
      $class = "Music";
      break;
      
    case "code":
      $class = "Code";
      break;
      
    case "twitter":
      $class = "Twitter";
      break;
      
    case "location":
      $class = "Location";
      break;
    
  }
  
  if ($row['source'] == "foursquare"){
    $class= "Location";
  }
  
  
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  $structure[$class][md5($row['title'])] = $row;
  
}


$q = sprintf("select post_title, ID, unix_timestamp(post_date) as epoch from aqcom_wp_posts where post_status = 'publish' and post_date between '%s' and '%s' order by post_date", date(DATE_ISO8601, $from), date(DATE_ISO8601, $to));


$results = mysql_query($q) or die(mysql_error());

while ($row = mysql_fetch_assoc($results)){
  
  $class = "Blog";
  
  $row['content'] = $row['post_title'];
  $row['title'] = $row['post_title'];
  $row['url'] = "http://www.aquarionics.com/?p=".$row['ID'];
  $row['icon'] = '';
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  $structure[$class][md5($row['title'])] = $row;
  
}

?>
<html>


<head>
<title>Nicholas Avenell - Web Developer</title>

<link rel="stylesheet" href="/style.css"/> 


</head>
<body>
<h1 id="header">Nicholas Avenell</h1>
<nav>[ <a href="http://hol.istic.net/Aquarion">Who?</a> | <a href="http://www.github.com/aquarion">Works</a> | <a href="http://www.linkedin.com/in/webperson">Worker</a> | <a href="http://www.aquarionics.com">Weblog</a> | <a href="http://hol.istic.net/Walrus">Walrus</a> ]</nav>
<h2 id="nav">
  <a href="<?PHP echo $backwards ?>" title="<?PHP echo $backwards_title ?>">&lt;</a>
  <?PHP echo $datetitle ?>
  <a href="<?PHP echo $onwards ?>"   title="<?PHP echo $onwards_title ?>">&gt;</a>
  
</h2>

<br clear="both"/>


<div id="tiles" >
<?PHP 

foreach($structure as $classname => $items){
  
  print '<div id="'.$classname.'" class="contentbox content">
  <h1>'.$classname.'</h1>
  <ul>
  ';
  
  foreach($items as $row){
    echo "<li>";
    if ($row['icon']){
      echo "<img src='".$row['icon']."'/>";
    }
    
    echo "<a href=\"".$row['url']."\">[".date("H:i", $row['epoch'])."] ".$row['content']."</a><br/></li>\n";
  }
  
  print '</ul>
  </div>';
}
  
?>
</div>

</body>
</html>
