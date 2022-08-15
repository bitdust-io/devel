<?php
?>
<!DOCTYPE html>
<html>
<head> 
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>phpBitAdmin - Bitcoin Mobile Wallet</title>
<link rel="stylesheet" href="http://code.jquery.com/mobile/1.4.5/jquery.mobile-1.4.5.min.css" />
<link rel="stylesheet" href="../css/m_phpbitadmin.css" />
<script src="http://code.jquery.com/jquery-1.11.1.min.js"></script>
<script src="http://code.jquery.com/mobile/1.4.5/jquery.mobile-1.4.5.min.js"></script>
<script src="jquery.qrcode.min.js"></script>

</head>
<body>
<div id="qrcode"></div>
</body>
<script type="text/javascript">
$('#qrcode').qrcode({width:600,height:600,text: "bitcoin:mujQyziBaVkh3vgcLZnBPFsBGypMkpTYCa?amount=0.002862&amp;label=&amp;message=Hello World!"});
</script>
</html>