
var w = 100;
var h = 50;

var Formatting = {

	'achivement' : function(object, element){

		if(element.hasClass("Raptr")){
			return element;
		}
		element.css("background-image", "url('"+object.image+"')");
		//element.css("background-size", "contain");
		element.addClass("achivement");
		//element.html("<span>"+decodeEntities(object.title).split(" – ")[0]+"</span>");;
		element.html("<div style=\"position: absolute; top: 2px; width: 100%; text-align: center; overflow: hidden\">"+decodeEntities(object.title).split(" – ")[0]+"</div>"
		+"<div style=\"position: absolute; bottom: 2px; text-align: center; width: 100%; overflow: hidden;\">"+decodeEntities(object.title).split(" – ")[1]+"</div>");;

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+decodeEntities(object.title))

		element.height(h*2 - 12);
		element.width(w*1 - 12);


		return element;
	},

	'kickstarter' :  function(object, element){

                element.css("background-image", "url('"+object.image+"')");
                element.css("background-size", "contain");
                element.addClass("achivement");
                element.html("");

                element.attr("title", (object.source+" "+object.type).capitalize()+": "+decodeEntities(object.title))

                element.height(h*2-12);
                element.width(w*2-12);

                return element;
        },

	'facebook' : function(object, element){
		//element.height(h*2);
		element.width(w*3-12);
		element.data("growthis", true);
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
		element.ready(Formatting.photoresize);
		return element;
	},

	'flickr' : function(object, element){

		element.addClass("photo");
		element.css("background-image", "url('"+object.image+"')");
		element.ready(Formatting.photoresize);

		element.html("")

		return element;
	},

	'Raptr' : function(object, element){

		element.addClass("gaming");
		element.removeClass("twitter");
		
		return element;
	},

	'Foursquare-Badge' : function(object, element){

		element.addClass("achivement");
		element.css("background-image", "url('"+object.image+"')");
		element.css("width", w);
		element.css("height", 3*h);
		element.css("background-size", "cover");

		element.html("")

		return element;
	},

	'fitbit' : function(object, element){
		element.html(element.html().replace("activeScore", "Active Score"));
		img = $('<img/>');
		img.addClass("icon")
		img.attr('src', "http://art.istic.net/iconography/fitbit.png");
		element.prepend(img);
		return element;
	},

	'aquarionics' : function(object, element){
		//element.height(200);
		element.height(h*3-12);
		element.width(w*3-12);

		if(object.image){
			element.css("background-image", "url('"+object.image+"')");
		} else {
			element.css("background", "rgba(0,0,0,.8)");
		}
		element.css("background-size", "cover");
		element.css("background-position", "center");
		element.html('<div class="bloginner">' + object.title + '</div><img src="http://art.istic.net/iconography/aqcom/logo_64.png" height="64" width="64" class="aqcomicon">');

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+decodeEntities(object.title))


		return element;
	},


	photoresize : function(thing){
		console.log(this);
		console.log(thing);
	}
};

Formatting.badge = Formatting.achivement;
Formatting.gaming = Formatting.achivement;
Formatting.rapr = false;
