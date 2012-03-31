
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
	width       : false,
	padding     : 10,
	columns     : false,
	animate     : false,
	
	linetemplate : false,

	getBestPosition : function (box){
			
		column = -1;
		if (TickyTacky.width == false){
			TickyTacky.width = box.outerWidth();
		}

		if (TickyTacky.currentline > 5){
			TickyTacky.currentline -= 5;
		}

		//TickyTacky.currentline = 0;

		columns = Math.round(box.outerWidth() / TickyTacky.width);
		height  = Math.round(box.height()     / TickyTacky.b);
		
		
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
						//console.log("found a fit at R"+TickyTacky.currentline+"/C"+column);
					}
				}
			}
			
			/*if (TickyTacky.grid[TickyTacky.currentline][0] == 0){
				column = 0;
			} else if (TickyTacky.grid[TickyTacky.currentline][1] == 0 && columns < 3){
				column = 1;
			} else if (TickyTacky.grid[TickyTacky.currentline][2] == 0 && columns < 2){
				column = 2;
			}*/
			
			if (column != -1){
				
				fit = true;
				for (i=column; i < columns; i++){
					if (TickyTacky.grid[TickyTacky.currentline][i] != 0){
						fit = false;
						//console.log(columns+" wide box failed a fit at R"+TickyTacky.currentline+"/C"+column);
						//console.log("Due to "+TickyTacky.currentline+"/C"+i+" = "+TickyTacky.grid[TickyTacky.currentline][i]);
						//console.log(TickyTacky.grid[TickyTacky.currentline]);
					}
				}
				if (fit != true){
					column = -1;
				}
			}
			if ( column == -1){
				TickyTacky.currentline = TickyTacky.currentline+1;
				if (TickyTacky.grid.length <= TickyTacky.currentline) {
					TickyTacky.grid[TickyTacky.currentline] = TickyTacky.linetemplate.slice(0);
				}
				
			}
		}


		left = column * (TickyTacky.width+TickyTacky.padding);
		

		top_offset = TickyTacky.currentline * (TickyTacky.b+TickyTacky.padding);

		//grid[currentline][column] = height;
		
		//if (height > 1){
			for (i=0;i<height;i++){
				while (TickyTacky.grid.length <= TickyTacky.currentline + i){
					TickyTacky.grid[TickyTacky.grid.length] = TickyTacky.linetemplate.slice(0);
				}
				TickyTacky.grid[TickyTacky.currentline+i][column] = height;
				if (columns > 1){
					TickyTacky.grid[TickyTacky.currentline+i][column+1] = height;
				}
				if (columns > 2){
					TickyTacky.grid[TickyTacky.currentline+i][column+2] = height;
				}
			}
		//}
		
		return [top_offset, left];
	},

	rearrange : function(){
	
		animate = true;
	
		boxwidth = $($('.contentbox')[0]).outerWidth();
		
		tileswidth = $(window).width();
		n = Math.floor(tileswidth/boxwidth);
		
		if (n > $('.contentbox').length -1){
			n = $('.contentbox').length -1;
		}
	
		if (n == TickyTacky.columns){
			return;
		}
		
		//console.log("Rearranging for "+n);
		
		
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
		
		
		boxes = new Array()

		$('.contentbox').each(function(){
			box = $(this)
			
			box.show();
						
			if (box.height() % TickyTacky.b && !box.hasClass("boxresized")){
				h = box.outerHeight();
				d = h - box.height();
				n = TickyTacky.b * (Math.floor(h/TickyTacky.b) +1);
				box.height(n-d);
				box.addClass("boxresized");
			}
			boxes.push(box);
			
		//});

		//for(k in boxes){
		
			//box = $(boxes[k])
		
			//$(boxes[k]).appendTo(t);
			//$(boxes[k]).appendTo(tl);
									
			if (box.outerWidth() > (TickyTacky.columns*TickyTacky.width)){
				//console.log(box);
				//box.css("overflow", "hidden");
				box.css("width", TickyTacky.columns*TickyTacky.width);
				//box.css("height", "auto");
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
			
		});//}

		TickyTacky.animate = true;
	}
	
	
}

