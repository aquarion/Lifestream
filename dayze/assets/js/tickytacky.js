/*   -------------------------------------------------------------------------
	 * @Name:        TickyTacky.js
	 * @Description: Javascript for making a mosaic of lots of divs, fitting neatly together.
	 *
	 * Currently designed mostly to work with my own LifeStream project, I intend
	 * make it more generic soon.
	 * 
	 *       
	 * @Author:    Nicholas Avenell <nicholas@aquarionics.com>
	 * @Year:      2011 -> 2012
	 * @Copyright: TickyTacky by Istic.Networks is licensed under a Creative Commons Attribution 3.0 Unported License.
	 * @Licence:   http://creativecommons.org/licenses/by/3.0/
	 * @url:       https://github.com/aquarion/Lifestream/blob/master/dayze/assets/js/tickytacky.js
	 *
	 * DEPENDENCIES
	 *  - jQuery.js
	 *-------------------------------------------------------------------------*/

TickyTacky = {

	grid        : false,
	currentline : 0,
	box_height  : 100,
	box_width   : 230,
	padding     : 2,
	margin      : 1,
	
	columns     : false,
	animate     : false,
	linetemplate : false,
	boxcount     : 0,

	getBestPosition : function (box){
	
		TickyTacky.boxcount = TickyTacky.boxcount + 1;
			
		column = -1;
		
		// Start looking from the top if we've got less than ten rows,
		// or a maximum of 5 rows back
		
		backfill = 20
		
		if (TickyTacky.currentline > backfill){
			TickyTacky.currentline -= backfill;
		} else {
			TickyTacky.currentline = 0;
		}
		
		columns = Math.round(box.outerWidth() / TickyTacky.box_width);
		rows    = Math.round(box.outerHeight()     / TickyTacky.box_height);
	
		n = 0;
		while (column == -1){
			n = n + 1;
			// If we've tried a hundred rows? We give up.
			if (n == 100){
				return;
			}
			
			// Check the current row to see if we can find a fit.
			for (i=0;  i< TickyTacky.columns;i++){
				if (column == -1 && TickyTacky.grid[TickyTacky.currentline][i] == 0){
					if ( TickyTacky.columns - (i + columns) >= 0 ){
						column = i;
					}
				}
			}
			
			// If we found one ...
			if (column != -1){
				fit = true; // Assumes it fits
				
				for (x=0; x < rows; x++){ // Iterate down the grid from our current position for the Height of the block
					if (TickyTacky.grid[TickyTacky.currentline+x]){ // If there *is* a row here
						
						for (y=0; y < columns; y++){ // Check
						
							// Check the line to make sure there's enough room.
							if (TickyTacky.grid[TickyTacky.currentline+x][column+y] != 0){
								fit = false; // It didn't fit.
							}
						}
					}
				}
				// Ah well, try another row...
				if (fit != true){
					column = -1;
				}
			}	
			
			
			if ( column == -1){ // If we didn't find a home...
				// Go down one row.
				TickyTacky.currentline = TickyTacky.currentline+1;
				if (TickyTacky.grid.length <= TickyTacky.currentline) {
					TickyTacky.grid[TickyTacky.currentline] = TickyTacky.linetemplate.slice(0);
				}
				
			}
			
		} // While column == -1
		
		

		// We have a place to put it! Time to work out the exact co-ordinates.
		
		
		left_offset = column * TickyTacky.box_width;
		top_offset  = TickyTacky.currentline * TickyTacky.box_height;
	
		// Pad out the grid to for the space/s we've just filled.
		while (TickyTacky.grid.length <= TickyTacky.currentline + rows){
			TickyTacky.grid[TickyTacky.grid.length] = TickyTacky.linetemplate.slice(0);
		}		
		
		// Now fill numbers in the grid where we've just put a thing.
		for (i=0;i<rows;i++){			
			for (j=0; j < columns; j++){
				TickyTacky.grid[TickyTacky.currentline+i][column+j] = rows;
			}
			
		}
		
		// Send back the new position.
		return [top_offset, left_offset];
	},

	rearrange : function( callBackOnCompletion ){
	
		playground_width          = $(window).width(); // Width of the play area.
		playground_width_in_boxes = Math.floor(playground_width/TickyTacky.box_width); 
														// How many boxes we can fit in that.

		if((($(".contentbox").length / playground_width_in_boxes) < 2) && playground_width_in_boxes >= 4 ){
			playground_width_in_boxes = 4;
		} else if((($(".contentbox").length / playground_width_in_boxes) < 3) && playground_width_in_boxes >= 6) {
			playground_width_in_boxes = 6;
		}
	
		if (playground_width_in_boxes == TickyTacky.columns){
			// If we've already rendered for this number of columns, go home.
			return;
		}
		
		TickyTacky.currentline = 0; // From the top, gentlemen
		TickyTacky.columns     = playground_width_in_boxes;
	
		// Set up a template for new grid rows
		TickyTacky.linetemplate = []
		for (i=0;  i< TickyTacky.columns;i++){
			TickyTacky.linetemplate[i] = 0;
		}
		TickyTacky.grid = [TickyTacky.linetemplate.slice(0)];
		// </>
				
				
		// Little boxes, little boxes, little boxes in Array.
		
		boxes = new Array() // Array of boxes to be positioned.
		
		$(".dwarfed").each(function(){
			box = $(this)
			box.removeClass("dwarfed")
			box.width(box.attr("originalwidth"));
		});

		// And they're all made out of TickyTacky...
		$('.contentbox').each(function(){
			box = $(this)
			
			box.show();
			// ... And they all look just the same.
			// Normalise the heights and widths of the boxes to a muliplyer of box_height/box_width
			if (!box.hasClass("boxresized")){
			
				border = parseInt(box.css("border-top-width")) + parseInt(box.css("border-bottom-width"));
				
				h = box.innerHeight();
				if(border){
					h += border;
				}
				w = box.outerWidth();
				
				height_in_boxes    = (Math.ceil(h/TickyTacky.box_height) );
				
				if(height_in_boxes == 0){
					height_in_boxes = 1;
				}
												
				outer_height_in_px       = TickyTacky.box_height * height_in_boxes;
				inner_height_to_get_that = outer_height_in_px - (h - box.height());
				box.height(inner_height_to_get_that - TickyTacky.padding);
				
				width_in_boxes          = (Math.round(w/TickyTacky.box_width) );
				if(width_in_boxes == 0){
					width_in_boxes = 1;
				}				
				outer_width_in_px       = TickyTacky.box_width * width_in_boxes;
				inner_width_to_get_that = outer_width_in_px - (w - box.width());
				box.width(inner_width_to_get_that - TickyTacky.padding);
								
			}
			boxes.push(box); // Add the box to the set of boxes to be positioned.
			
			
			// If the box is too big, shrink it to a saner size. Bit hacky.
			if (box.outerWidth() > (TickyTacky.columns*TickyTacky.box_width)){
				box.attr("originalwidth", box.outerWidth());
				box.addClass("dwarfed");
				box.css("width", TickyTacky.columns*TickyTacky.box_width);
			}
			
			// Get the new position
			box.css("position", "absolute");
			position = TickyTacky.getBestPosition(box)
			
			// Move it into place, in a pretty fashion if we want to.
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
		
		max_columns = 0;
		
		for (i=0;  i < TickyTacky.grid.length;i++){
			row = TickyTacky.grid[i];
			for (k=0;  k< TickyTacky.columns;k++){
				if (row[k] && k > max_columns){
					max_columns = k
				}
			}
		}
		
		max_columns += 1;
		
		// Resize the playground to fit the columns perfectly.
		newTilesWidth = TickyTacky.box_width * max_columns;
		
		if (newTilesWidth != $('#tiles').width()){		
		
			// Animate that, if we want to
			if(TickyTacky.animate){
				$('#tiles').animate({
					width : newTilesWidth
					}, 500 );
					
			} else {
				$('#tiles').css("width", newTilesWidth);
			}
		}
		

		// Animate the future ones.
		// Initial render isn't animated because it makes the browser cry.
		TickyTacky.animate = true;
		
		// Operator, get me information.
		if(jQuery.isFunction( callBackOnCompletion )){
			callBackOnCompletion();
		}
		
		// And that's us gone for the night.
		return;
	}
	
	
}

