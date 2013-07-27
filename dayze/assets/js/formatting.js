
var Formatting = {

	'achivement' : function(object, element){

		element.css("background-image", "url('"+object.image+"')");
		element.addClass("achivement");
		element.html("");

		element.attr("title", (object.source+" "+object.type).capitalize()+": "+decodeEntities(object.title))

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

	'Raptr' : function(object, element){

		element.addClass("gaming");
		element.removeClass("twitter");

		return element;
	},

	'Foursquare-Badge' : function(object, element){

		element.addClass("achivement");
		element.css("background-image", "url('"+object.image+"')");
		element.css("width", "100");
		element.css("height", "100");
		element.css("background-size", "cover");

		element.html("")

		return element;
	},

	'fitbit' : function(object, element){
		element.html(element.html().replace("activeScore", "Active Score"));
		img = $('<img/>');
		img.attr('src', "http://liveart.istic.net/iconography/fitbit.png");
		element.prepend(img);
		return element;
	},


};

Formatting.badge = Formatting.achivement;