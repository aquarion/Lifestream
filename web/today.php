<?PHP
require("library.php");

$dbcxn = getDatabase();

$dateformat = "l j<\s\u\p>S</\s\u\p> F Y";

if (isset($_GET['year']) && isset($_GET['month']) && isset($_GET['day'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $d = intval($_GET['day']);  
  
  $from = mktime(0,0,0,$m,$d,$y);
  $to = mktime(23,59,59,$m,$d,$y);
  
  $datetitle = date($dateformat, $from);
  
} elseif (isset($_GET['year']) && isset($_GET['month'])){
  $y = intval($_GET['year']);
  $m = intval($_GET['month']);  
  $from = mktime(0,0,0,$m,1,$y);
  $to = mktime(23,59,59,$m,date("t", $from),$y);
  
  
  $datetitle = date($dateformat, $from)." to ".date($dateformat, $to);
  
} elseif (isset($_GET['year'])){
  $y = intval($_GET['year']);
  
  $from = mktime(0,0,0,1,1,$y);
  $to = mktime(23,59,59,12,31,$y);
  
} else {
  $from = mktime(0,0);
  $to = mktime(23,59,59);
  
  $datetitle = date($dateformat, $from);
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
    
  }
  
  
  
  if (!isset($structure[$class])){
    $structure[$class] = array();
  }
  
  $structure[$class][md5($row['title'])] = $row;
  
}


?>
<html>
<head>

<style type="text/css">

body {
  background: #EEE;
  font-family: "Trebuchet MS";
}

#Games {
  background-color: #1a82f7;
  background: -moz-linear-gradient(100% 100% 90deg, #64A8F5, #1a82f7);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#1a82f7), to(#64A8F5));
}

#Twitter {
  background-color: #50BFEB;
  background: -moz-linear-gradient(100% 100% 90deg, #50BFEB, #B5DAE8);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#50BFEB), to(#B5DAE8));
}

#Twitter {
  background-color: #50BFEB;
  background: -moz-linear-gradient(100% 100% 90deg, #50BFEB, #B5DAE8);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#50BFEB), to(#B5DAE8));
}

#Music {
  backgroud: #B266DE;
  background: -moz-linear-gradient(100% 100% 90deg, #B266DE, #DBC0EB);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#B266DE), to(#DBC0EB));
}

#Code {
  backgroud: #E8965F;
  background: -moz-linear-gradient(100% 100% 90deg, #E8965F, #E6B595);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#E8965F), to(#E6B595));
}

#Other {
  backgroud: #4EB34B;
  background: -moz-linear-gradient(100% 100% 90deg, #4EB34B, #CFE3CF);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#4EB34B), to(#CFE3CF));
}

.contentbox {
  border: 1px solid #666;
  border-top-color: #CCC;
  border-left-color: #CCC;
  border-bottom: none;
  width: 15em;
  float: left;
  
  background-color: #666;
  background: -moz-linear-gradient(100% 100% 90deg, #EEE, #333);
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(#EEE), to(#333));
  margin: .2em;
  padding: 0 0 0 0;
  
  -border-radius: 2em;
}

.contentbox ul {
  list-style: none;
  padding-top: 1em;
  padding-left: 0em;
  display: block;
  padding: 0 0 0 0;
  margin: 0 0 0 0;
  overflow: hidden;
}

.contentbox li {
  padding: 1em;
  border-bottom: 1px solid #666;
  border-top: 1px solid #EEE;
}

.contentbox h1 {
  color: #EEE;
  padding: 0;
  margin: 0;
  position: relative;
  top: -.2em;
  border-bottom: 1px solid #666;
}

.contentbox img {
  float: left;
  margin: .2em;
  max-width: 64px;
}

.contentbox br {
  
  clear: both;
}

</style>
</head>
<body>
<h1>Nicholas Avenell</h1>
<h2><?PHP echo $datetitle ?></h2>

<br clear="both"/>

<?PHP 

foreach($structure as $classname => $items){
  
  print '<div id="'.$classname.'" class="contentbox">
  <h1>'.$classname.'</h1>
  <ul>
  ';
  
  foreach($items as $row){
    echo "<li><img src='".$row['icon']."'/> ".$row['content']."<br/></li>\n";
  }
  
  print '</ul>
  </div>';
}
  
?>

  <!--
<div id="Games" class="contentbox">
  <h1>Played</h1>
  <ul>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
  </ul>
</div>
<div id="Music" class="contentbox">
  <h1>Heard</h1>
  <ul>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
  </ul>
</div>
<div id="Code" class="contentbox">
  <h1>Coded</h1>
  <ul>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
  </ul>
</div>
<div id="Twitter" class="contentbox">
  <h1>Tweeted</h1>
  <ul>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
  </ul>
</div>
<div id="Other" class="contentbox">
  <h1>Also</h1>
  <ul>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
    <li>Did this thing</li>
  </ul>
</div>
-->
</body>
</html>