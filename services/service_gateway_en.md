
Description:
The service gateway() is the entry point to send and receive service data packets and communicate with other nodes in the BitPie.NET network. This is a sort of "gates" - all useful traffic for client software is passed through it.
The main two methods inbox() and outbox() process incoming and outgoing packets, digitally signed by data owner. The package body can also be encrypted by owner key, before will be passed to the method oubox(). Event handlers call methods in other services of the client software when receiving and transmitting packets appears.
The service gateway() also counts the payload traffic of the software.
