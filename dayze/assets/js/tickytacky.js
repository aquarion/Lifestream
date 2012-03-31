
var Move =	{

  copy	:   function(e, target)	{
	    var eId      = $(e);
	    var copyE    = eId.cloneNode(true);
	    var cLength  = copyE.childNodes.length -1;
	    copyE.id     = e+'-copy';

	    for(var i = 0; cLength >= i;  i++)	{
	    if(copyE.childNodes[i].id) {
	    var cNode   = copyE.childNodes[i];
	    var firstId = cNode.id;
	    cNode.id    = firstId+'-copy'; }
	    }
	    $(target).append(copyE);
	    },
  element:  function(e, target, type)	{
	    var eId =  $(e);
	    if(type == 'move') {
	       $(target).append(eId);
	    }

	    else if(type == 'copy')	{
	       this.copy(e, target);
	    }
	    }
}


TickyTacky = {

	grid        : false,
	currentline : 0,
	b           : 200,
	width       : 230,
	maxwidth    : 2,
	padding     : 10,
	margin      : 5,
	columns     : false,
	animate     : false,
	
	linetemplate : false,
	
	boxcount     : 0,

	getBestPosition : function (box){
	
		TickyTacky.boxcount = TickyTacky.boxcount + 1;
			
		column = -1;
		if (TickyTacky.width == false){
			TickyTacky.width = box.outerWidth();
		}

		if (TickyTacky.currentline > 5){
			TickyTacky.currentline -= 5;
		} else {
			TickyTacky.currentline = 0;
		}
		columns = Math.round(box.outerWidth() / TickyTacky.width);
		height  = Math.round(box.height()     / TickyTacky.b);
		
		debug = "";
		debug = debug + "\nInfo:" + TickyTacky.boxcount + ": "+ columns+"x"+height+"\n";
		
		n = 0;
		//console.log(box);
		while (column == -1){
			n = n + 1;
			if (n == 100){
				////console.log(box);
				//console.log("Giving Up");
				return;
			}
			
			for (i=0;  i< TickyTacky.columns;i++){
				if (column == -1 && TickyTacky.grid[TickyTacky.currentline][i] == 0){
					if ( TickyTacky.columns - (i + columns) >= 0 ){
						column = i;
						debug += "found a fit at R"+TickyTacky.currentline+"/C"+column+"\n";
					}
				}
			}
						
			if (column != -1){
				//debug = debug + "Width Check: "+TickyTacky.grid[TickyTacky.currentline].join(",")+"\n";
				fit = true;
				
				for (x=0; x < height; x++){
					if (TickyTacky.grid[TickyTacky.currentline+x]){
						//debug = debug + "Checking "+x+"\n";
						for (y=0; y < columns; y++){
							debug = debug + "Checking "+x+"/"+y+"\n";
							if (TickyTacky.grid[TickyTacky.currentline+x][column+y] != 0){
								fit = false;
								//console.log(columns+" wide box failed a fit at R"+TickyTacky.currentline+"/C"+column);
								//console.log("Due to "+TickyTacky.currentline+"/C"+y+" = "+TickyTacky.grid[TickyTacky.currentline][i]);
								//console.log(TickyTacky.grid[TickyTacky.currentline]);
							}
						}
					}
				}
				if (fit != true){
					column = -1;
				}
			}	
			
			
			if ( column == -1){
				TickyTacky.currentline = TickyTacky.currentline+1;
				debug = debug + "increase current line\n";
				if (TickyTacky.grid.length <= TickyTacky.currentline) {
					TickyTacky.grid[TickyTacky.currentline] = TickyTacky.linetemplate.slice(0);
				}
				
			}
		}
		
		

		left = column * (TickyTacky.width+TickyTacky.padding);

		top_offset = TickyTacky.currentline * (TickyTacky.b+TickyTacky.padding);
	
		while (TickyTacky.grid.length <= TickyTacky.currentline + height){
			TickyTacky.grid[TickyTacky.grid.length] = TickyTacky.linetemplate.slice(0);
		}		
		
		debug = debug + "Starting at "+(TickyTacky.currentline)+"/"+column+" to "+columns+"\n";
		
		for (i=0;i<height;i++){			
			for (j=0; j < columns; j++){
				debug = debug + (TickyTacky.currentline+i) + "/" + (column+j) +" = "+height+"\n";
				TickyTacky.grid[TickyTacky.currentline+i][column+j] = height;
			}
			
		}
		
		for ( i=TickyTacky.currentline;i<TickyTacky.grid.length;i++ ){
			line = TickyTacky.grid[i]
			debug = debug + line.join(",") + "\n";
		}
		
		/*debug = debug + "\n Current: " + TickyTacky.grid[TickyTacky.currentline].join(",");
			
		if(TickyTacky.grid[TickyTacky.currentline+1]){
			debug = debug + "\n Next:" + TickyTacky.grid[TickyTacky.currentline+1].join(",");
		}*/
		
			
		//$(box).attr("title", debug);
		//$(box).html("<pre>"+debug+"</pre>");
		
		//console.log(debug);
	
		return [top_offset, left];
	},

	rearrange : function(){
	
		animate = true;
	
		boxwidth = TickyTacky.width;//$($('.contentbox')[0]).outerWidth();
		
		tileswidth = $(window).width();
		n = Math.floor(tileswidth/(boxwidth+TickyTacky.padding));
		
		if (n > $('.contentbox').length -1){
			n = $('.contentbox').length -1;
		}
	
		if (n == TickyTacky.columns){
			return;
		}
		
		console.log("Rearranging for "+n);
		
		
		TickyTacky.currentline = 0;
		TickyTacky.width       = boxwidth;
		TickyTacky.columns     = n;
	
		TickyTacky.linetemplate = []
		for (i=0;  i< TickyTacky.columns;i++){
			TickyTacky.linetemplate[i] = 0;
		}
		
		TickyTacky.grid = [TickyTacky.linetemplate.slice(0)];
		

		t  = $('#tiles');
		tl = $('#tilelist');
		
		if(TickyTacky.animate){
			
			$('#tiles').animate({
				width : (TickyTacky.width + TickyTacky.padding) * TickyTacky.columns
				}, 1500 );
				
		} else {
			$('#tiles').css("width",(TickyTacky.width + TickyTacky.padding) * TickyTacky.columns);
		}
		
		console.log("Tiles Width: "+ $('#tiles').width());
		
		boxes = new Array()

		$('.contentbox').each(function(){
			box = $(this)
			
			box.show();
						
			if (box.height() % TickyTacky.b && !box.hasClass("boxresized")){
				h = box.outerHeight();
				d = h - box.height();
				height_in_boxes = (Math.ceil(h/TickyTacky.b) );
				
				if (height_in_boxes == 0){
					height_in_boxes = 1;
				}
				n = TickyTacky.b * height_in_boxes + ((height_in_boxes-1)*TickyTacky.padding);
				box.height(n-d);
				
				
				h = box.width();
				
				width_in_boxes = (Math.ceil(h/TickyTacky.width) );
				
				n = TickyTacky.width * width_in_boxes;
				
				newwidth = n - (TickyTacky.padding* (TickyTacky.columns - width_in_boxes));
				
				box.width(newwidth);
				
				box.attr("title", newwidth+" "+width_in_boxes);
				
				box.addClass("boxresized");
				
				
			}
			boxes.push(box);
									
			if (box.outerWidth() > (TickyTacky.columns*TickyTacky.width)){
				box.css("width", TickyTacky.columns*TickyTacky.width);
			}
			
			position = TickyTacky.getBestPosition(box)
			
			box.css("position", "absolute");
			
			if(TickyTacky.animate){
				box.animate({
					top: position[0],
					left: position[1]
				}, 1000);
			} else {
				box.css("top", position[0]);
				box.css("left", position[1]);
			}
			
		})

		TickyTacky.animate = true;
	}
	
	
}

