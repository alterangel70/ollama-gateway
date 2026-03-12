"""
Application use cases — orchestration of domain logic and infrastructure ports.
"""
import time

from ..domain.entities import LLMRequest, LLMResponse
from ..domain.ports import ILLMProvider, ILogger, IMetrics


class GenerateTextUseCase:
    """Orchestrates an LLM text generation request end-to-end.

    Coordinates the LLM provider, structured logger, and metrics collector
    without depending on any concrete infrastructure implementation.
    """
    
    def __init__(
        self,
        llm_provider: ILLMProvider,
        logger: ILogger,
        metrics: IMetrics
    ):
        self.llm = llm_provider
        self.logger = logger
        self.metrics = metrics
    
    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Run the generation request and return the response.

        Records Prometheus metrics for latency, token usage, and request counts.
        Always resets the active-requests gauge in the finally block.
        """
        start_time = time.time()
        
        self.logger.info(
            "LLM generation started",
            request_id=str(request.id),
            model=request.model,
            prompt_length=len(request.prompt),
            temperature=request.temperature
        )
        
        self.metrics.set_gauge("llm_active_requests", 1)
        self.metrics.record_histogram(
            "llm_prompt_length",
            len(request.prompt),
            {"model": request.model}
        )
        
        try:
            response = await self.llm.generate(request)
            
            duration = time.time() - start_time

            self.metrics.increment_counter(
                "llm_requests_total",
                labels={"model": request.model, "status": "success"}
            )
            self.metrics.record_histogram("llm_duration_seconds", duration, {"model": request.model})
            self.metrics.record_histogram("llm_tokens_total", response.tokens_used["input"], {"model": request.model, "type": "input"})
            self.metrics.record_histogram("llm_tokens_total", response.tokens_used["output"], {"model": request.model, "type": "output"})
            self.metrics.set_gauge("llm_last_request_timestamp", time.time())
            
            self.logger.info(
                "LLM generation completed",
                request_id=str(request.id),
                model=request.model,
                tokens_input=response.tokens_used["input"],
                tokens_output=response.tokens_used["output"],
                duration_seconds=round(duration, 3)
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.increment_counter(
                "llm_requests_total",
                labels={"model": request.model, "status": "error"}
            )
            self.logger.error(
                "LLM generation failed",
                error=e,
                request_id=str(request.id),
                model=request.model,
                duration_seconds=round(duration, 3)
            )
            raise

        finally:
            self.metrics.set_gauge("llm_active_requests", 0)
