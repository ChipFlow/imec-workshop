.global flashio_worker_begin
.global flashio_worker_end

.balign 4

flashio_worker_begin:
# a0 ... data pointer
# a1 ... data length
# a2 ... optional WREN cmd (0 = disable)

mv t3, ra

# address of SPI ctrl reg
li   t0, 0xb0000000
# enter bypass mode
lbu   t1, 0(t0) 
ori   t1, t1, 0x1
sb    t1, 0(t0)
call flashio_wait_bypass_ready

beqz a2, flashio_xfer

sb a2, 8(t0) # send wren
call flashio_wait_bypass_ready
li t1, 2 # deselect
sb t1, 4(t0)
call flashio_wait_bypass_ready

flashio_xfer:
beqz a1, flashio_done
lbu t1, 0(a0)
sb t1, 8(t0) # tx data
call flashio_wait_bypass_ready
lbu t1, 12(t0) # rx data
sb t1, 0(a0)
addi a0, a0, 1
addi a1, a1, -1
j flashio_xfer

flashio_done:
# exit bypass mode
lbu   t1, 0(t0) 
andi   t1, t1, 0xFE
sb    t1, 0(t0)

fence.i
mv ra, t3
ret

flashio_wait_bypass_ready:
lbu   t1, 4(t0)
andi t1, t1, 0x1
beqz t1, flashio_wait_bypass_ready
ret

.balign 4
flashio_worker_end:
