
import jq

def eval_jq(input, args):
    if len(args) != 1:
        raise Exception("jq requires a single argument")

    filt = jq.compile(args[0])

    if type(input) == str:
        ret = filt.input_text(input).all()
    else:
        ret = filt.input_value(input).all()

    return ret
