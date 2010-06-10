
lifestream = {}

lifestream.init = function(){

	$('#lifestream').tabs({
		spinner: '<img src="/assets/spinner.gif">'
		});

	
	setTimeout(lifestream.refresh, 15000);


	$('#lifestream').bind('tabsshow', function(event, ui) {

		// Objects available in the function context:
		ui.tab     // anchor element of the selected (clicked) tab
		ui.panel   // element, that contains the selected/clicked tab contents
		ui.index   // zero-based index of the selected (clicked) tab


	});


}

lifestream.refresh = function(){
	var $tabs = $('#lifestream').tabs();
	var selected = $tabs.tabs('option', 'selected'); // => 0

	selected = $('#lifestream>ul li')[selected];

	data = false;
	url = '/misc/lifestream/';
	if ($($('a', selected)[0]).attr("rel"))
	{
		data = { "filter" : $($('a', selected)[0]).attr("rel") }
	}


	$.post(url, data, lifestream.update, "json");
}

lifestream.update = function (data){

	data.reverse();

	$(data).each(function(){
		
		if ($('#'+this['id']).length == 0 )
		{
			content = 
			"<a href=\""+this['url']+"\">"
				+"<img src='"+this['icon']+"'/ height=\"16px\">"
			+"</a>"
			+"<span>"+this['content']+"</span>"
			+"<span class=\"moreinfo\">"
			+ this['source']+"<br/>"
			+"<a class=\"nicetime\" href=\""+this['url']+"\">"+this['nicetime']+" ago</a>"
			+"</span>";


			object = document.createElement("DIV");
			object.id = this['id'];
			object.className = "lifestream "+this['type'];

			$(object).html(content);
			

			$(object).css("display", "none");

			$('#lifestreamContent').prepend(object);

			$('#'+this['id']).show("slow");

		} else {
			$('#'+this['id']+" .nicetime").html(this['nicetime']+" ago");
			//#$('#'+this['id']+" .nicetime").hide("slow",
			//#	function(){
			//		$('#'+this['id']+" .nicetime").html(this['nicetime']);
			//		$('#'+this['id']+" .nicetime").show("slow");
			//});
			
		}

		if ($('#lifestreamContent div.lifestream').length > 10)
		{
			for (i = 0; i < $('#lifestreamContent div.lifestream').length; i++ )
			{	
				if (i > 19)
				{
					id = $('#lifestreamContent div.lifestream')[i].id;
					$('#'+id).fadeOut("slow", $('#'+id).remove());
				}
			}
		}

	});
	
	
	setTimeout(lifestream.refresh, 10000);

}

//#$(document).ready(lifestream.init);

