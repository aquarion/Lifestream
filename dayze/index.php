<!DOCTYPE>
<html>
<head>
	<script src="http://code.jquery.com/jquery-1.10.2.min.js"></script>
	<script src="/assets/js/packery.pkgd.min.js"></script>
<link href='http://fonts.googleapis.com/css?family=Goudy+Bookletter+1911' rel='stylesheet' type='text/css'>

<style type="text/css">
body {
  font-family: 'Goudy Bookletter 1911', "Georgia", serif;
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
	margin-left: auto;
	margin-right: auto;
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
}
 
header .buttons {
	text-align: center;
}

	.item {
	width:  178px;
	height:  78px;
		overflow: hidden;
		background: #eee;
		padding: 10px;
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
	width:  378px;
	height:  178px;
}

.tumblr {
  background: rgba(125,96,103, .4);
  background: -moz-linear-gradient(100% 100% 30deg, rgba(16,125,158, .8), rgba(16,158,151, .8));
  background: -webkit-gradient(linear, 0% 0%, 50% 40%, from(rgba(16,125,158, .8)), to(rgba(16,158,151, .8)));
  color: white;
}

.twitter {
	width:  228px;
	quotes:"\201C""\201D""\2018""\2019";
	width:  278px;

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
	width:  178px;
	font-family: monospace;
}

.oyster_oyster {
	width: 78px;
  background: -moz-linear-gradient(100% 100% 30deg, rgba(27,80,224, .8), rgba(27,126,224, .8));
  background: -webkit-gradient(linear, 0% 0%, 50% 100%, from(rgba(27,80,224, .8)), to(rgba(27,126,224, .8)));
	background-image: url('http://liveart.istic.net/iconography/tfl_grad.png');
	background-size: cover;
	background-position: center center;
	background-repeat: none;
	color: white;
}

.photo {
	width: 460px;
	height: 360px;
	padding: 0;
	background-size: cover;
	background-color: rgba(0,0,0,.8);
	background-position: center center;
	background-repeat: none;


	border-width: 20px 20px 20px 20px;
	-moz-border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	-webkit-border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	-o-border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	border-image: url(http://liveart.istic.net/images/gold-frame.png) 20 20 20 20 stretch;
	margin: 0;
	position: relative;
}


.gaming {
  background-color: rgba(26,130,247, .4);
  background: -moz-linear-gradient(100% 100% 90deg, rgba(100, 168, 245, .5), rgba(26,130,247, .4));
  background: -webkit-gradient(linear, 0% 0%, 0% 100%, from(rgba(100, 168, 245, .4)), to(rgba(26,130,247, .4)));
}

</style>

<script type="text/javascript">

var packeryInstance = false;
var mostRecent      = 0;
var nextDate = new Date(0);

var Formatting = {

	'lastfm' : function(object, element){
		return false;
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

		element.addClass("photo");
		element.css("background-image", "url('"+object.image+"')");
		element.css("width", "160");
		element.css("height", "160");

		element.html("")

		return element;
	},

};

var NicAve = {
	init : function(){
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

	success : function(data, status, xhdr){
		var container = document.querySelector('#tiles');

		$('#message').html(data.message);

		$(data.items).each(function(){
			item = $('<a class="item"></a>');
			item.addClass(this['source'])
			item.addClass(this['type'])
			item.addClass(this['source']+'_'+this['type']);



			item.html(this['title'])

			item.data("object", this);

			/*item.click(function(){
				console.log($(this).data("object"));
				return false;
			})*/

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

			if (data.direction = "append"){
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

		if (data.offset){
			console.log("Going in "+data.next+" seconds with an offset of "+data.offset)
			setTimeout(function(){NicAve.fetchNext(data.offset)}, data.next * 1000);
		} else {
			console.log("Finished this block");
			console.log("Going in "+data.next+" seconds with after of "+nextDate.toISOString())
			setTimeout(function(){NicAve.fetchUpdate(nextDate.toISOString())}, data.next * 1000);
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