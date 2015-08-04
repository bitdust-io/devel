if (typeof String.prototype.trimLeft !== 'function') {
	String.prototype.trimLeft = function(charlist) {
	  if (charlist === undefined)
	    charlist = "\s";
	  return this.replace(new RegExp("^[" + charlist + "]+"), "");
	};
}

if (typeof String.prototype.trimRight !== 'function') {
	String.prototype.trimRight = function(charlist) {
		  if (charlist === undefined)
		    charlist = "\s";
		  return this.replace(new RegExp("[" + charlist + "]+$"), "");
	};
}

if (typeof String.prototype.trim !== 'function') {
	String.prototype.trim = function(charlist) {
		  return this.trimLeft(charlist).trimRight(charlist);
	};
}

if (typeof String.prototype.endsWith !== 'function') {
    String.prototype.endsWith = function(suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}
