<!DOCTYPE>
<html>
<head>
	<script src="http://code.jquery.com/jquery-1.10.2.min.js"></script>
	<script src="/assets/js/packery.pkgd.min.js"></script>
	<script type="text/javascript" src="https://www.google.com/jsapi"></script>

<link href='http://fonts.googleapis.com/css?family=PT+Mono|Raleway|Comfortaa' rel='stylesheet' type='text/css'>

<style type="text/css">
body {
  font-family: 'Raleway', sans-serif;
  color: #000040;
  padding: 0 0 0 0;
  margin: 0 0 0 0;

  /*background: #FFF url('../img/tweetcloud.png') no-repeat fixed center center;*/
background-attachment: fixed;
background-color: #EEE;
background-image: url(http://dailyphoto.aquarionics.com/redirect.php);
background-position: 50% 50%;
background-repeat: repeat;
background-size: cover;
color: white;
}

#tiles {
	font-size: 10pt;
	margin-left: auto;
	margin-right: auto;
	margin: 0 3em;
}

header {
	max-width: 760px;
	background: rgba(0,0,0,.8);
	color: white;
	margin-left: auto;
	margin-right: auto;
	border-bottom-right-radius: 2em;
	border-bottom-left-radius: 2em;
}

header a {
	color: white;
}

header p {
	padding: 0em 1em 0 1em;
}

header h1 {
	background: rgba(0,0,100,.8);
	font-size: 4em;
	text-align: center;
	padding: 0em 1em 0 1em;
	margin-bottom: 0em ;
  	font-family: 'Comfortaa', sans-serif;
}
 
header .buttons {
	text-align: center;
}

#message {
	text-align: center;
}

	.item {
	width:  188px;
		overflow: hidden;
		background: #eee;
		padding: 5px;
  background: rgba(125,96,103, .4);
  background: -moz-linear-gradient(100% 100% 30deg, rgba(125,96,103, .9), rgba(184,163,168, .9));
  background: -webkit-gradient(linear, 0% 0%, 50% 100%, from(rgba(125,96,103, .9)), to(rgba(184,163,168, .9)));
  text-decoration: none;
  color: white;
  border-top: 1px solid rgba(255,255,255,.3);
  border-left:  1px solid rgba(255,255,255,.3);
  border-bottom:    1px solid rgba(0,0,0,.3);
  border-right:   1px solid rgba(0,0,0,.3);
  position: relative;
	}

	.item img {
		float: right;
		max-height: 64px;
	}

.tumblr_quote {
	quotes:"\201C""\201D""\2018""\2019";
	width:  388px;
}

.tumblr {
  background: rgba(125,96,103, .4);
  background: -moz-linear-gradient(100% 100% 30deg, rgba(16,125,158, .8), rgba(16,158,151, .8));
  background: -webkit-gradient(linear, 0% 0%, 50% 40%, from(rgba(16,125,158, .8)), to(rgba(16,158,151, .8)));
  color: white;
}

.tumblr blockquote {
	padding-left: 0;
	margin-left: 0;
}

.twitter {
	quotes:"\201C""\201D""\2018""\2019";
	width:  288px;

  background: rgba(125,96,103, .4);
  background: -moz-linear-gradient(100% 100% 30deg, rgba(27,80,224, .8), rgba(27,126,224, .8));
  background: -webkit-gradient(linear, 0% 0%, 50% 100%, from(rgba(27,80,224, .8)), to(rgba(27,126,224, .8)));
  color: white;
}

.location {
  background: rgba(224,109,27, .4);
  background: -moz-linear-gradient(100% 100% 30deg, rgba(224,109,27, .8), rgba(224,162,27, .8));
  background: -webkit-gradient(linear, 0% 0%, 50% 100%, from(rgba(224,109,27, .8)), to(rgba(224,162,27, .8)));
}

.tumblr_quote:before {
	color:#ccc;
	content:open-quote;
	font-size:4em;
	line-height:.1em;
	margin-right:.25em;
	vertical-align:-.4em;
}

.github {
	background: rgba(0,0,0,.8);
	color: limegreen;
	width:  188px;
  	font-family: 'PT Mono', monospace;
}

.oyster_oyster {
	width: 88px;
  background: -moz-linear-gradient(100% 100% 30deg, rgba(27,80,224, .8), rgba(27,126,224, .8));
  background: -webkit-gradient(linear, 0% 0%, 50% 100%, from(rgba(27,80,224, .8)), to(rgba(27,126,224, .8)));
	background-image: url('http://liveart.istic.net/iconography/tfl_grad.png');
	background-size: cover;
	background-position: center center;
	background-repeat: no-repeat;
	color: white;
}

.photo {
	width: 460px;
	height: 360px;
	padding: 0;
	background-size: contain;
	background-color: rgba(0,0,0,.8);
	background-position: center center;
	background-repeat: no-repeat;


	border-width: 20px 20px 20px 20px;
	-moz-border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	-webkit-border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	-o-border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	margin: 0;
	position: relative;
}

.tumblr_photo {
	width: 160px;
	height: 160px;
	border-style: solid;
border-width: 20;
-moz-border-image: url(http://liveart.istic.net/images/lt_teal_frame_wide.gif) 17 17 17 17 repeat;
-webkit-border-image: url(http://liveart.istic.net/images/lt_teal_frame_wide.gif) 17 17 17 17 repeat;
-o-border-image: url(http://liveart.istic.net/images/lt_teal_frame_wide.gif) 17 17 17 17 repeat;
border-image: url(http://liveart.istic.net/images/lt_teal_frame_wide.gif) 17 17 17 17 fill repeat;
}

.gaming {
  background-color: rgba(26,130,247, .4);
  background: -moz-linear-gradient(100% 100% 90deg, rgba(100, 168, 245, .5), rgba(26,130,247, .4));
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(rgba(100, 168, 245, .4)), to(rgba(26,130,247, .4)));
}

.item cite {
	font-size: 8pt;
	position: absolute;
	bottom: 0;
	left: 0;
	width: 100%;
	padding: 1px;
	background: rgba(0,0,0,.3);
	color: white;
	display: none;
	text-align: left;
}

.item:hover cite {
	display: block;
}

.centered {
	text-align: center;
}

.achivement {
	border: 0;
	height: 100;
	width: 100;
	margin: 0;
	padding: 0;
	position: relative;

	background-color: rgba(0,0,0,.8);
	background-position: center center;
	background-repeat: no-repeat;
}

#music_chart, #music_others {
	width:  388px;
	background: rgba(255,255,255,.6);
	color: #333;
}

</style>

<script type="text/javascript">
      	google.load("visualization", "1", {packages:["corechart"]});

var packeryInstance = false;
var mostRecent      = 0;
var nextDate = new Date(0);

function decodeEntities(s){
    var str, temp= document.createElement('p');
    temp.innerHTML= s;
    str= temp.textContent || temp.innerText;
    temp=null;
    return str;
}

var Formatting = {

	'achivement' : function(object, element){

		element.css("background-image", "url('"+object.image+"')");
		element.addClass("achivement");
		element.html("");

		element.attr("title", decodeEntities(object.title))

		element.height(100);
		element.width(100);

		return element;
	},

	'oyster' : function(object, element){

		var journey = element.html();

		journey = journey.replace(/\[.*?\]/, '');

		element.addClass("centered");
		element.html(journey);
		return element;

	},

	'lastfm' : function(object, element){
		split = object.title.split(' \u2013 ');
		artist = split[0]

		if(NicAve.lastfm[artist]){
			NicAve.lastfm[artist] += 1;
		} else {
			NicAve.lastfm[artist] = 1;
		}
		return false
	},

	'tumblr_photo' : function(object, element){

		element.css("background-image", "url('"+object.image+"')");
		element.addClass("photo");
		element.html("")

		return element;
	},

	'flickr' : function(object, element){

		element.addClass("photo");
		element.css("background-image", "url('"+object.image+"')");

		element.html("")

		return element;
	},

	'Foursquare-Badge' : function(object, element){

		element.addClass("achivement");
		element.css("background-image", "url('"+object.image+"')");
		element.css("width", "160");
		element.css("height", "160");

		element.html("")

		return element;
	},

};


Formatting.fitbit_badge = Formatting.achivement;
Formatting.steambadge = Formatting.achivement;
Formatting.steam_steam = Formatting.achivement;


var NicAve = {

	lastfm : {},

	music_chart : false,

	init : function(){
      	google.setOnLoadCallback(NicAve.loadTiles);
	},

	loadTiles : function(){

		var container = document.querySelector('#tiles');
		packeryInstance = new Packery( container, { 'gutter' : 0} );

		NicAve.fetchNext(0)
	},

	fetchNext : function(offset){
		var data = {'path': window.location.pathname}
		if(offset){
			data.offset = offset;
		}
		$.ajax({
		  type: "POST",
		  url: '/fetchNext.php',
		  data: data,
		  success:  NicAve.success,
		  error:  NicAve.error,
		  dataType: 'json'
		});
	},

	fetchUpdate : function(mostRecent){
		var data = { 'after': mostRecent, 'path': window.location.pathname}
		$.ajax({
		  type: "POST",
		  url: '/fetchNext.php',
		  data: data,
		  success:  NicAve.success,
		  error:  NicAve.error,
		  dataType: 'json'
		});
	},

	build_music_chart : function(){
		if(Object.keys(NicAve.lastfm).length == 0){
			return;
		}

		data = [];
		other = 0;
		others = []

		total = 0;

		for (artist in NicAve.lastfm){
			total += NicAve.lastfm[artist];
		}

		for (artist in NicAve.lastfm){
			value = NicAve.lastfm[artist];
			if (value < 5 ){
				other += value;
				others.push(artist)
			} else {
				datum = [artist, value]
				data.push(datum)
			}
		}


		if(other > 0){
			data.push(["Others", other]);
		}

        var options = {
          "title" : "Music",
          'chartArea': {'width': '90%', 'height': '90%'},
          'backgroundColor' : 'transparent'
        };

		var container = document.querySelector('#tiles');

		if(!NicAve.music_chart){
			chartBox = $('<div id="music_chart"/>');
			$(container).append( chartBox );
			packeryInstance.appended( chartBox );
		}

		var data = google.visualization.arrayToDataTable(data);
		NicAve.music_chart = new google.visualization.PieChart(document.getElementById('music_chart'));

		height = Math.ceil( (total*.75) / 50) * 50;
		width  = Math.ceil( (total) / 100) * 100
		maxwidth = $(container).width();

		if (height > (maxwidth*.75)) {
			height = maxwidth*.75;
		}
		if (width > (maxwidth)) {
			width = maxwidth;
		}

		if(width < 300){
			height = 300;
			width = 400;
		}

		$('#music_chart').height(height);
		$('#music_chart').width(width);

		if(!$('#music_others').length){
			chartBox = $('<div id="music_others"/>');
			chartBox.addClass("item");
			$(container).append( chartBox );
			packeryInstance.appended( chartBox );
		}
		if(others.length > 1){
			plus = others.pop();
			$('#music_others').html("'Others' includes "+others.join(", ")+" &amp; "+plus);
		}


		NicAve.music_chart.draw(data, options);

	},

	success : function(data, status, xhdr){
		var container = document.querySelector('#tiles');

		$('#message').html(data.message);

		$(data.items).each(function(){
			item = $('<a class="item"></a>');
			item.addClass(this['source'])
			item.addClass(this['type'])
			item.addClass(this['source']+'_'+this['type']);

			if(!this['title'] && !this['image']){
				return;
			}

			item.html(this['title'])

			item.data("object", this);

			item.click(function(){
				//console.log($(this).data("object"));
				//return false;
			})


			if(this.image && this.image != 0){
				img = $('<img/>');
				img.attr('src', this.image);
				item.prepend(img);
			}
			if(this.url && this.url != 0){
				item.attr("href", this.url);
			}

			if( Formatting[this['source']] ){
				item = Formatting[this['source']](this, item)
			}
			if( Formatting[this['type']] ){
				item = Formatting[this['type']](this, item)
			}
			if( Formatting[this['source']+'_'+this['type']] ){
				item = Formatting[this['source']+'_'+this['type']](this, item)
			}

			if(!item){
				return;
			}

			cite = $("<cite/>")
			cite.html(this['source']+"@"+this['date_created']);
			item.append(cite);


			if (data.direction == "append"){
				$(container).append( item );
				packeryInstance.appended( item );
			} else {
				$(container).prepend( item );
				packeryInstance.prepended( item );
			}


			if(this['epoch'] > mostRecent){
				mostRecent = this['epoch'];
			}
			updated = new Date(this['date_updated'])
			if (updated > nextDate){
				nextDate = updated;
			}
		})

		NicAve.build_music_chart();

		$(".item").each(function(){
			item = $(this);
			if(!item.hasClass("photo") && !item.hasClass("achivement")){
				height = $(item).height()+12;
				if($("img", item).length){
					imgheight = $("img", item).height();
					if(imgheight > height){
						height = imgheight;
					}
				}
				nearest50 = Math.ceil( height / 50) * 50;
				item.height(nearest50-12);
			}
		});
		packeryInstance.layout();

		if (data.offset){
			setTimeout(function(){NicAve.fetchNext(data.offset)}, data.next * 1000);
		} else {
			//setTimeout(function(){NicAve.fetchUpdate(nextDate.toISOString())}, data.next * 1000);
		}
	},

	error : function(header, status, error){
		console.log(status);
		console.log(error);
	}
}

$(document).ready(NicAve.init);

</script>

</head>
<body>

<header>
<h1>Nicholas Avenell</h1>
<p>Is still working on this site</p>
<p>I am Nicholas Avenell. I am a professional geek. I've worked for <a href="http://wiki.aquarionics.com/placesIveWorked">various companies</a>, some of which you might have heard of. I have <a href="http://www.aquarionics.com/">a weblog</a>, which I update sometimes; this, which updates more often; and <a href="http://istic.net">a company</a> which does stuff you could hire me for. I've got accounts pretty much everywhere you'd expect, greatest hits are below, the rest you'll find on the page confusingly named <a href="http://wiki.aquarionics.com/walrus">Project Walrus</a>.</p>
<p>
	<p class="buttons"><a href="http://www.twitter.com/aquarion"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/twitter.png" title="" alt="" /></a> <a href="http://www.linkedin.com/in/webperson"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/linkedin.png" title="" alt="" /></a> <a href="http://www.facebook.com/aquarion"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/facebook.png" title="" alt="" /></a> <a href="http://www.last.fm/user/Aquarion"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/lastfm.png" title="" alt="" /></a>  <a href="http://www.flickr.com/people/aquarion"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/flickr.png" title="" alt="" /></a> <a href="http://aquarion.tumblr.com/"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/tumblr.png" title="" alt="" /></a> <a href="http://www.reddit.com/user/Aquarion/"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/reddit.png" title="" alt="" /></a> <a href="https://plus.google.com/106823138194139107308/posts"><img src="http://art.istic.net/iconography/elegantmediaicons/PNG/google.png" title="" alt="" /></a></p>
</p>
<p id="message" />
</header>

  <div id="tiles" class="container">
  </div>

</body>
</html>
