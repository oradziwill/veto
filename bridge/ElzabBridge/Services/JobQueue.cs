using System.Threading.Channels;
using ElzabBridge.Models;

namespace ElzabBridge.Services;

public interface IFiscalJobQueue
{
    ValueTask EnqueueAsync(FiscalPrintReceiptRequest request, CancellationToken cancellationToken);
    IAsyncEnumerable<FiscalPrintReceiptRequest> DequeueAllAsync(CancellationToken cancellationToken);
}

public sealed class FiscalJobQueue : IFiscalJobQueue
{
    private readonly Channel<FiscalPrintReceiptRequest> _channel =
        Channel.CreateUnbounded<FiscalPrintReceiptRequest>(
            new UnboundedChannelOptions { SingleReader = true, SingleWriter = false }
        );

    public ValueTask EnqueueAsync(FiscalPrintReceiptRequest request, CancellationToken cancellationToken) =>
        _channel.Writer.WriteAsync(request, cancellationToken);

    public async IAsyncEnumerable<FiscalPrintReceiptRequest> DequeueAllAsync(
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken
    )
    {
        while (await _channel.Reader.WaitToReadAsync(cancellationToken))
        {
            while (_channel.Reader.TryRead(out var item))
            {
                yield return item;
            }
        }
    }
}
